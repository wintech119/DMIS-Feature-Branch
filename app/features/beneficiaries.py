"""
DMIS - Beneficiary Management Feature

Provides CRUD operations for managing beneficiaries (individuals and shelters)
for last-mile distribution tracking.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

from app.db import db
from app.db.models import Beneficiary, Parish, Warehouse, Agency
from app.core.decorators import feature_required
from app.core.audit import add_audit_fields


beneficiaries_bp = Blueprint('beneficiaries', __name__, url_prefix='/lastmile/beneficiaries')

BENEFICIARY_TYPES = ['INDIVIDUAL', 'SHELTER']
STATUS_CODES = [('A', 'Active'), ('I', 'Inactive')]


def validate_beneficiary_data(form_data, is_update=False, beneficiary_id=None):
    """Validate beneficiary form data"""
    errors = {}
    
    beneficiary_type = form_data.get('beneficiary_type', '').strip()
    if not beneficiary_type:
        errors['beneficiary_type'] = 'Beneficiary type is required'
    elif beneficiary_type not in BENEFICIARY_TYPES:
        errors['beneficiary_type'] = 'Invalid beneficiary type'
    
    beneficiary_name = form_data.get('beneficiary_name', '').strip()
    if not beneficiary_name:
        errors['beneficiary_name'] = 'Beneficiary name is required'
    elif len(beneficiary_name) > 120:
        errors['beneficiary_name'] = 'Beneficiary name cannot exceed 120 characters'
    
    parish_code = form_data.get('parish_code', '').strip()
    if not parish_code:
        errors['parish_code'] = 'Parish is required'
    
    phone_no = form_data.get('phone_no', '').strip()
    if phone_no and len(phone_no) > 20:
        errors['phone_no'] = 'Phone number cannot exceed 20 characters'
    
    email_text = form_data.get('email_text', '').strip()
    if email_text and len(email_text) > 100:
        errors['email_text'] = 'Email cannot exceed 100 characters'
    
    return len(errors) == 0, errors


@beneficiaries_bp.route('/')
@login_required
@feature_required('lastmile_management')
def list_beneficiaries():
    """List all beneficiaries with filter tabs"""
    filter_type = request.args.get('filter', 'all')
    search_query = request.args.get('search', '').strip()
    
    total_count = Beneficiary.query.count()
    individual_count = Beneficiary.query.filter_by(beneficiary_type='INDIVIDUAL').count()
    shelter_count = Beneficiary.query.filter_by(beneficiary_type='SHELTER').count()
    active_count = Beneficiary.query.filter_by(status_code='A').count()
    
    counts = {
        'total': total_count,
        'individual': individual_count,
        'shelter': shelter_count,
        'active': active_count
    }
    
    query = Beneficiary.query
    
    if filter_type == 'individual':
        query = query.filter_by(beneficiary_type='INDIVIDUAL')
    elif filter_type == 'shelter':
        query = query.filter_by(beneficiary_type='SHELTER')
    elif filter_type == 'active':
        query = query.filter_by(status_code='A')
    
    if search_query:
        search_pattern = f'%{search_query}%'
        query = query.filter(
            db.or_(
                Beneficiary.beneficiary_name.ilike(search_pattern),
                Beneficiary.given_name.ilike(search_pattern),
                Beneficiary.family_name.ilike(search_pattern),
                Beneficiary.community_text.ilike(search_pattern)
            )
        )
    
    beneficiaries = query.order_by(Beneficiary.beneficiary_name).all()
    
    return render_template(
        'beneficiaries/index.html',
        beneficiaries=beneficiaries,
        counts=counts,
        filter_type=filter_type,
        search_query=search_query
    )


@beneficiaries_bp.route('/create', methods=['GET', 'POST'])
@login_required
@feature_required('lastmile_management')
def create():
    """Create a new beneficiary"""
    if request.method == 'POST':
        is_valid, errors = validate_beneficiary_data(request.form)
        
        if not is_valid:
            for field, error in errors.items():
                flash(error, 'danger')
            
            parishes = Parish.query.order_by(Parish.parish_name).all()
            hsa_warehouses = Warehouse.query.filter_by(tier_code='HSA').order_by(Warehouse.warehouse_name).all()
            agencies = Agency.query.order_by(Agency.agency_name).all()
            
            return render_template(
                'beneficiaries/create.html',
                parishes=parishes,
                hsa_warehouses=hsa_warehouses,
                agencies=agencies,
                beneficiary_types=BENEFICIARY_TYPES,
                status_codes=STATUS_CODES,
                form_data=request.form,
                errors=errors
            )
        
        try:
            from app.security.param_validation import safe_id
            
            beneficiary_type = request.form.get('beneficiary_type').strip()
            
            registered_hsa_id = safe_id(request.form.get('registered_hsa_id'))
            if registered_hsa_id <= 0:
                registered_hsa_id = None
            
            shelter_agency_id = safe_id(request.form.get('shelter_agency_id'))
            if shelter_agency_id <= 0:
                shelter_agency_id = None
            
            beneficiary = Beneficiary(
                beneficiary_type=beneficiary_type,
                beneficiary_name=request.form.get('beneficiary_name').strip().upper(),
                given_name=request.form.get('given_name', '').strip().upper() or None,
                family_name=request.form.get('family_name', '').strip().upper() or None,
                phone_no=request.form.get('phone_no', '').strip() or None,
                email_text=request.form.get('email_text', '').strip() or None,
                parish_code=request.form.get('parish_code').strip(),
                community_text=request.form.get('community_text', '').strip() or None,
                address1_text=request.form.get('address1_text', '').strip() or None,
                address2_text=request.form.get('address2_text', '').strip() or None,
                registered_hsa_id=registered_hsa_id,
                shelter_agency_id=shelter_agency_id,
                status_code=request.form.get('status_code', 'A').strip(),
                notes=request.form.get('notes', '').strip() or None
            )
            
            add_audit_fields(beneficiary, current_user, is_new=True)
            
            db.session.add(beneficiary)
            db.session.commit()
            
            flash(f'Beneficiary "{beneficiary.beneficiary_name}" created successfully.', 'success')
            return redirect(url_for('beneficiaries.list_beneficiaries'))
            
        except IntegrityError:
            db.session.rollback()
            flash('A beneficiary with this name already exists.', 'danger')
            parishes = Parish.query.order_by(Parish.parish_name).all()
            hsa_warehouses = Warehouse.query.filter_by(tier_code='HSA').order_by(Warehouse.warehouse_name).all()
            agencies = Agency.query.order_by(Agency.agency_name).all()
            return render_template(
                'beneficiaries/create.html',
                parishes=parishes,
                hsa_warehouses=hsa_warehouses,
                agencies=agencies,
                beneficiary_types=BENEFICIARY_TYPES,
                status_codes=STATUS_CODES,
                form_data=request.form,
                errors={}
            )
            
        except Exception:
            db.session.rollback()
            current_app.logger.exception('Error creating beneficiary')
            flash('An unexpected error occurred. Please try again or contact support.', 'danger')
            parishes = Parish.query.order_by(Parish.parish_name).all()
            hsa_warehouses = Warehouse.query.filter_by(tier_code='HSA').order_by(Warehouse.warehouse_name).all()
            agencies = Agency.query.order_by(Agency.agency_name).all()
            return render_template(
                'beneficiaries/create.html',
                parishes=parishes,
                hsa_warehouses=hsa_warehouses,
                agencies=agencies,
                beneficiary_types=BENEFICIARY_TYPES,
                status_codes=STATUS_CODES,
                form_data=request.form,
                errors={}
            )
    
    parishes = Parish.query.order_by(Parish.parish_name).all()
    hsa_warehouses = Warehouse.query.filter_by(tier_code='HSA').order_by(Warehouse.warehouse_name).all()
    agencies = Agency.query.order_by(Agency.agency_name).all()
    
    return render_template(
        'beneficiaries/create.html',
        parishes=parishes,
        hsa_warehouses=hsa_warehouses,
        agencies=agencies,
        beneficiary_types=BENEFICIARY_TYPES,
        status_codes=STATUS_CODES
    )


@beneficiaries_bp.route('/<int:beneficiary_id>')
@login_required
@feature_required('lastmile_management')
def view(beneficiary_id):
    """View beneficiary details"""
    beneficiary = Beneficiary.query.get_or_404(beneficiary_id)
    return render_template('beneficiaries/view.html', beneficiary=beneficiary)


@beneficiaries_bp.route('/<int:beneficiary_id>/edit', methods=['GET', 'POST'])
@login_required
@feature_required('lastmile_management')
def edit(beneficiary_id):
    """Edit existing beneficiary"""
    beneficiary = Beneficiary.query.get_or_404(beneficiary_id)
    
    if request.method == 'POST':
        submitted_version = request.form.get('version_nbr', type=int)
        if submitted_version != beneficiary.version_nbr:
            flash('This beneficiary record has been modified by another user. Please reload and try again.', 'warning')
            return redirect(url_for('beneficiaries.view', beneficiary_id=beneficiary_id))
        
        is_valid, errors = validate_beneficiary_data(request.form, is_update=True, beneficiary_id=beneficiary_id)
        
        if not is_valid:
            for field, error in errors.items():
                flash(error, 'danger')
            
            parishes = Parish.query.order_by(Parish.parish_name).all()
            hsa_warehouses = Warehouse.query.filter_by(tier_code='HSA').order_by(Warehouse.warehouse_name).all()
            agencies = Agency.query.order_by(Agency.agency_name).all()
            
            return render_template(
                'beneficiaries/edit.html',
                beneficiary=beneficiary,
                parishes=parishes,
                hsa_warehouses=hsa_warehouses,
                agencies=agencies,
                beneficiary_types=BENEFICIARY_TYPES,
                status_codes=STATUS_CODES,
                form_data=request.form,
                errors=errors
            )
        
        try:
            from app.security.param_validation import safe_id
            
            registered_hsa_id = safe_id(request.form.get('registered_hsa_id'))
            if registered_hsa_id <= 0:
                registered_hsa_id = None
            
            shelter_agency_id = safe_id(request.form.get('shelter_agency_id'))
            if shelter_agency_id <= 0:
                shelter_agency_id = None
            
            beneficiary.beneficiary_type = request.form.get('beneficiary_type').strip()
            beneficiary.beneficiary_name = request.form.get('beneficiary_name').strip().upper()
            beneficiary.given_name = request.form.get('given_name', '').strip().upper() or None
            beneficiary.family_name = request.form.get('family_name', '').strip().upper() or None
            beneficiary.phone_no = request.form.get('phone_no', '').strip() or None
            beneficiary.email_text = request.form.get('email_text', '').strip() or None
            beneficiary.parish_code = request.form.get('parish_code').strip()
            beneficiary.community_text = request.form.get('community_text', '').strip() or None
            beneficiary.address1_text = request.form.get('address1_text', '').strip() or None
            beneficiary.address2_text = request.form.get('address2_text', '').strip() or None
            beneficiary.registered_hsa_id = registered_hsa_id
            beneficiary.shelter_agency_id = shelter_agency_id
            beneficiary.status_code = request.form.get('status_code', 'A').strip()
            beneficiary.notes = request.form.get('notes', '').strip() or None
            
            add_audit_fields(beneficiary, current_user, is_new=False)
            
            db.session.commit()
            
            flash('Beneficiary updated successfully.', 'success')
            return redirect(url_for('beneficiaries.view', beneficiary_id=beneficiary_id))
            
        except StaleDataError:
            db.session.rollback()
            flash('This beneficiary record has been modified by another user. Please reload and try again.', 'warning')
            return redirect(url_for('beneficiaries.view', beneficiary_id=beneficiary_id))
            
        except Exception:
            db.session.rollback()
            current_app.logger.exception('Error updating beneficiary')
            flash('An unexpected error occurred. Please try again or contact support.', 'danger')
            
            parishes = Parish.query.order_by(Parish.parish_name).all()
            hsa_warehouses = Warehouse.query.filter_by(tier_code='HSA').order_by(Warehouse.warehouse_name).all()
            agencies = Agency.query.order_by(Agency.agency_name).all()
            
            return render_template(
                'beneficiaries/edit.html',
                beneficiary=beneficiary,
                parishes=parishes,
                hsa_warehouses=hsa_warehouses,
                agencies=agencies,
                beneficiary_types=BENEFICIARY_TYPES,
                status_codes=STATUS_CODES,
                form_data=request.form,
                errors={}
            )
    
    parishes = Parish.query.order_by(Parish.parish_name).all()
    hsa_warehouses = Warehouse.query.filter_by(tier_code='HSA').order_by(Warehouse.warehouse_name).all()
    agencies = Agency.query.order_by(Agency.agency_name).all()
    
    return render_template(
        'beneficiaries/edit.html',
        beneficiary=beneficiary,
        parishes=parishes,
        hsa_warehouses=hsa_warehouses,
        agencies=agencies,
        beneficiary_types=BENEFICIARY_TYPES,
        status_codes=STATUS_CODES
    )
