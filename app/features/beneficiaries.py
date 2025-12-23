"""
Beneficiary Management Routes (CUSTODIAN Role)

This module implements CRUD operations for beneficiaries (individuals and shelters)
management with strict validation, business rules, and RBAC.

Permission-Based Access Control:
- All operations restricted to CUSTODIAN role via @feature_required decorator

Beneficiary Types:
- INDIVIDUAL: Individual persons receiving relief
- SHELTER: Emergency shelters receiving relief supplies
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError
from sqlalchemy import or_
import re

from app.db import db
from app.db.models import Beneficiary, HSA, Parish, Agency
from app.core.decorators import feature_required
from app.core.audit import add_audit_fields
from app.core.phone_utils import validate_phone_format, get_phone_validation_error

beneficiaries_bp = Blueprint('beneficiaries', __name__, url_prefix='/beneficiaries')

BENEFICIARY_TYPES = ['INDIVIDUAL', 'SHELTER']
STATUS_CODES = ['A', 'I']


def validate_email(email):
    """Validate email format"""
    if not email:
        return True
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validate_beneficiary_data(form_data, is_update=False, beneficiary_id=None):
    """
    Validate beneficiary data against all business rules.
    Returns (is_valid, errors_dict)
    """
    errors = {}
    
    beneficiary_type = form_data.get('beneficiary_type', '').strip()
    beneficiary_name = form_data.get('beneficiary_name', '').strip()
    given_name = form_data.get('given_name', '').strip()
    family_name = form_data.get('family_name', '').strip()
    phone_no = form_data.get('phone_no', '').strip()
    email_text = form_data.get('email_text', '').strip()
    parish_code = form_data.get('parish_code', '').strip()
    status_code = form_data.get('status_code', '').strip()
    
    if not beneficiary_type:
        errors['beneficiary_type'] = 'Beneficiary type is required'
    elif beneficiary_type not in BENEFICIARY_TYPES:
        errors['beneficiary_type'] = f'Beneficiary type must be one of: {", ".join(BENEFICIARY_TYPES)}'
    
    if not beneficiary_name:
        errors['beneficiary_name'] = 'Beneficiary name is required'
    elif len(beneficiary_name) > 160:
        errors['beneficiary_name'] = 'Beneficiary name must not exceed 160 characters'
    
    if beneficiary_type == 'INDIVIDUAL':
        if given_name and len(given_name) > 80:
            errors['given_name'] = 'Given name must not exceed 80 characters'
        if family_name and len(family_name) > 80:
            errors['family_name'] = 'Family name must not exceed 80 characters'
    
    if phone_no:
        if not validate_phone_format(phone_no):
            errors['phone_no'] = get_phone_validation_error('Phone number')
    
    if email_text:
        if len(email_text) > 100:
            errors['email_text'] = 'Email must not exceed 100 characters'
        elif not validate_email(email_text):
            errors['email_text'] = 'Invalid email format'
    
    if parish_code:
        parish = Parish.query.filter_by(parish_code=parish_code).first()
        if not parish:
            errors['parish_code'] = 'Invalid parish code selected'
    
    if not status_code:
        errors['status_code'] = 'Status is required'
    elif status_code not in STATUS_CODES:
        errors['status_code'] = 'Status must be A (Active) or I (Inactive)'
    
    return (len(errors) == 0, errors)


@beneficiaries_bp.route('/')
@login_required
@feature_required('beneficiary_management')
def list_beneficiaries():
    """List all beneficiaries with filtering and search"""
    current_filter = request.args.get('filter', 'all').strip().lower()
    search_query = request.args.get('search', '').strip()
    type_filter = request.args.get('type', '').strip().upper()
    hsa_id_filter = request.args.get('hsa_id', type=int)
    
    total_count = Beneficiary.query.count()
    active_count = Beneficiary.query.filter_by(status_code='A').count()
    individual_count = Beneficiary.query.filter_by(beneficiary_type='INDIVIDUAL').count()
    shelter_count = Beneficiary.query.filter_by(beneficiary_type='SHELTER').count()
    
    counts = {
        'total': total_count,
        'active': active_count,
        'individual': individual_count,
        'shelter': shelter_count
    }
    
    query = Beneficiary.query
    
    if current_filter == 'active':
        query = query.filter_by(status_code='A')
    elif current_filter == 'inactive':
        query = query.filter_by(status_code='I')
    
    if type_filter in BENEFICIARY_TYPES:
        query = query.filter_by(beneficiary_type=type_filter)
    
    if hsa_id_filter:
        query = query.filter_by(registered_hsa_id=hsa_id_filter)
    
    if search_query:
        search_pattern = f'%{search_query}%'
        query = query.filter(
            or_(
                Beneficiary.beneficiary_name.ilike(search_pattern),
                Beneficiary.given_name.ilike(search_pattern),
                Beneficiary.family_name.ilike(search_pattern),
                Beneficiary.community_text.ilike(search_pattern)
            )
        )
    
    beneficiaries = query.order_by(Beneficiary.beneficiary_name).all()
    hsas = HSA.query.filter_by(status_code='A').order_by(HSA.hsa_code).all()
    
    return render_template(
        'beneficiaries/list.html',
        beneficiaries=beneficiaries,
        counts=counts,
        current_filter=current_filter,
        search_query=search_query,
        type_filter=type_filter,
        hsa_id_filter=hsa_id_filter,
        hsas=hsas,
        beneficiary_types=BENEFICIARY_TYPES
    )


@beneficiaries_bp.route('/create', methods=['GET', 'POST'])
@login_required
@feature_required('beneficiary_management')
def create_beneficiary():
    """Create new beneficiary"""
    if request.method == 'POST':
        is_valid, errors = validate_beneficiary_data(request.form)
        
        if not is_valid:
            for field, error in errors.items():
                flash(error, 'danger')
            
            parishes = Parish.query.order_by(Parish.parish_name).all()
            hsas = HSA.query.filter_by(status_code='A').order_by(HSA.hsa_code).all()
            return render_template(
                'beneficiaries/create.html',
                parishes=parishes,
                hsas=hsas,
                beneficiary_types=BENEFICIARY_TYPES,
                form_data=request.form,
                errors=errors
            )
        
        try:
            from app.security.param_validation import safe_id
            
            beneficiary = Beneficiary()
            beneficiary.beneficiary_type = request.form.get('beneficiary_type').strip()
            beneficiary.beneficiary_name = request.form.get('beneficiary_name').strip()
            beneficiary.given_name = request.form.get('given_name', '').strip() or None
            beneficiary.family_name = request.form.get('family_name', '').strip() or None
            beneficiary.phone_no = request.form.get('phone_no', '').strip() or None
            beneficiary.email_text = request.form.get('email_text', '').strip() or None
            beneficiary.parish_code = request.form.get('parish_code', '').strip() or None
            beneficiary.community_text = request.form.get('community_text', '').strip() or None
            beneficiary.address1_text = request.form.get('address1_text', '').strip() or None
            beneficiary.address2_text = request.form.get('address2_text', '').strip() or None
            
            hsa_id = request.form.get('registered_hsa_id', '').strip()
            if hsa_id:
                hsa_id_int = safe_id(hsa_id)
                if hsa_id_int > 0:
                    beneficiary.registered_hsa_id = hsa_id_int
            
            beneficiary.status_code = request.form.get('status_code', 'A').strip()
            
            add_audit_fields(beneficiary, current_user, is_new=True)
            
            db.session.add(beneficiary)
            db.session.commit()
            
            flash(f'Beneficiary "{beneficiary.beneficiary_name}" created successfully', 'success')
            return redirect(url_for('beneficiaries.list_beneficiaries', filter='all'))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.exception('Error creating beneficiary')
            flash('An error occurred while creating the beneficiary. Please try again or contact support.', 'danger')
            
            parishes = Parish.query.order_by(Parish.parish_name).all()
            hsas = HSA.query.filter_by(status_code='A').order_by(HSA.hsa_code).all()
            return render_template(
                'beneficiaries/create.html',
                parishes=parishes,
                hsas=hsas,
                beneficiary_types=BENEFICIARY_TYPES,
                form_data=request.form
            )
    
    parishes = Parish.query.order_by(Parish.parish_name).all()
    hsas = HSA.query.filter_by(status_code='A').order_by(HSA.hsa_code).all()
    return render_template(
        'beneficiaries/create.html',
        parishes=parishes,
        hsas=hsas,
        beneficiary_types=BENEFICIARY_TYPES
    )


@beneficiaries_bp.route('/<int:beneficiary_id>')
@login_required
@feature_required('beneficiary_management')
def view_beneficiary(beneficiary_id):
    """View beneficiary details"""
    beneficiary = Beneficiary.query.get_or_404(beneficiary_id)
    return render_template('beneficiaries/view.html', beneficiary=beneficiary)


@beneficiaries_bp.route('/<int:beneficiary_id>/edit', methods=['GET', 'POST'])
@login_required
@feature_required('beneficiary_management')
def edit_beneficiary(beneficiary_id):
    """Edit existing beneficiary"""
    beneficiary = Beneficiary.query.get_or_404(beneficiary_id)
    
    if request.method == 'POST':
        submitted_version = request.form.get('version_nbr', type=int)
        if submitted_version != beneficiary.version_nbr:
            flash('This record was updated by another user. Please reload and try again.', 'warning')
            return redirect(url_for('beneficiaries.view_beneficiary', beneficiary_id=beneficiary_id))
        
        is_valid, errors = validate_beneficiary_data(request.form, is_update=True, beneficiary_id=beneficiary_id)
        
        if not is_valid:
            for field, error in errors.items():
                flash(error, 'danger')
            
            parishes = Parish.query.order_by(Parish.parish_name).all()
            hsas = HSA.query.filter_by(status_code='A').order_by(HSA.hsa_code).all()
            return render_template(
                'beneficiaries/edit.html',
                beneficiary=beneficiary,
                parishes=parishes,
                hsas=hsas,
                beneficiary_types=BENEFICIARY_TYPES,
                form_data=request.form,
                errors=errors
            )
        
        try:
            from app.security.param_validation import safe_id
            
            beneficiary.beneficiary_type = request.form.get('beneficiary_type').strip()
            beneficiary.beneficiary_name = request.form.get('beneficiary_name').strip()
            beneficiary.given_name = request.form.get('given_name', '').strip() or None
            beneficiary.family_name = request.form.get('family_name', '').strip() or None
            beneficiary.phone_no = request.form.get('phone_no', '').strip() or None
            beneficiary.email_text = request.form.get('email_text', '').strip() or None
            beneficiary.parish_code = request.form.get('parish_code', '').strip() or None
            beneficiary.community_text = request.form.get('community_text', '').strip() or None
            beneficiary.address1_text = request.form.get('address1_text', '').strip() or None
            beneficiary.address2_text = request.form.get('address2_text', '').strip() or None
            
            hsa_id = request.form.get('registered_hsa_id', '').strip()
            if hsa_id:
                hsa_id_int = safe_id(hsa_id)
                if hsa_id_int > 0:
                    beneficiary.registered_hsa_id = hsa_id_int
            else:
                beneficiary.registered_hsa_id = None
            
            beneficiary.status_code = request.form.get('status_code', 'A').strip()
            
            add_audit_fields(beneficiary, current_user, is_new=False)
            
            db.session.commit()
            
            flash(f'Beneficiary "{beneficiary.beneficiary_name}" updated successfully', 'success')
            return redirect(url_for('beneficiaries.list_beneficiaries', filter='all'))
            
        except StaleDataError:
            db.session.rollback()
            flash('This record was updated by another user. Please reload and try again.', 'warning')
            return redirect(url_for('beneficiaries.view_beneficiary', beneficiary_id=beneficiary_id))
        except Exception as e:
            db.session.rollback()
            current_app.logger.exception('Error updating beneficiary')
            flash('An error occurred while updating the beneficiary. Please try again or contact support.', 'danger')
            
            parishes = Parish.query.order_by(Parish.parish_name).all()
            hsas = HSA.query.filter_by(status_code='A').order_by(HSA.hsa_code).all()
            return render_template(
                'beneficiaries/edit.html',
                beneficiary=beneficiary,
                parishes=parishes,
                hsas=hsas,
                beneficiary_types=BENEFICIARY_TYPES,
                form_data=request.form
            )
    
    parishes = Parish.query.order_by(Parish.parish_name).all()
    hsas = HSA.query.filter_by(status_code='A').order_by(HSA.hsa_code).all()
    return render_template(
        'beneficiaries/edit.html',
        beneficiary=beneficiary,
        parishes=parishes,
        hsas=hsas,
        beneficiary_types=BENEFICIARY_TYPES
    )


@beneficiaries_bp.route('/<int:beneficiary_id>/delete', methods=['POST'])
@login_required
@feature_required('beneficiary_management')
def delete_beneficiary(beneficiary_id):
    """Delete beneficiary with FK reference checks"""
    beneficiary = Beneficiary.query.get_or_404(beneficiary_id)
    
    try:
        beneficiary_name = beneficiary.beneficiary_name
        db.session.delete(beneficiary)
        db.session.commit()
        
        flash(f'Beneficiary "{beneficiary_name}" deleted successfully', 'success')
        return redirect(url_for('beneficiaries.list_beneficiaries'))
        
    except IntegrityError:
        db.session.rollback()
        flash('This beneficiary cannot be deleted because it is referenced by other records.', 'danger')
        return redirect(url_for('beneficiaries.view_beneficiary', beneficiary_id=beneficiary_id))
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception('Error deleting beneficiary')
        flash('An error occurred while deleting the beneficiary. Please try again or contact support.', 'danger')
        return redirect(url_for('beneficiaries.view_beneficiary', beneficiary_id=beneficiary_id))
