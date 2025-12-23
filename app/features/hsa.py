"""
HSA Management Routes (CUSTODIAN Role)

This module implements CRUD operations for Humanitarian Service Agencies (HSA)
management with strict validation, business rules, and RBAC.

Permission-Based Access Control:
- All operations restricted to CUSTODIAN role via @feature_required decorator

HSA Categories:
- JDF: Jamaica Defence Force
- MLSS: Ministry of Labour and Social Security
- PARISH_COUNCIL: Parish Council
- OTHER: Other Humanitarian Service Agency
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError
from sqlalchemy import or_

from app.db import db
from app.db.models import HSA, Custodian
from app.core.decorators import feature_required
from app.core.audit import add_audit_fields

hsa_bp = Blueprint('hsa', __name__, url_prefix='/hsa')

HSA_CATEGORIES = ['JDF', 'MLSS', 'PARISH_COUNCIL', 'OTHER']
HSA_CATEGORY_LABELS = {
    'JDF': 'Jamaica Defence Force',
    'MLSS': 'Ministry of Labour and Social Security',
    'PARISH_COUNCIL': 'Parish Council',
    'OTHER': 'Other Humanitarian Service Agency'
}
STATUS_CODES = ['A', 'I']


def validate_hsa_data(form_data, is_update=False, hsa_id=None):
    """
    Validate HSA data against all business rules.
    Returns (is_valid, errors_dict)
    """
    errors = {}
    
    hsa_code = form_data.get('hsa_code', '').strip().upper()
    hsa_category = form_data.get('hsa_category', '').strip()
    custodian_id = form_data.get('custodian_id', '').strip()
    status_code = form_data.get('status_code', '').strip()
    
    if not hsa_code:
        errors['hsa_code'] = 'HSA Code is required'
    elif len(hsa_code) > 30:
        errors['hsa_code'] = 'HSA Code must not exceed 30 characters'
    else:
        query = HSA.query.filter(db.func.upper(HSA.hsa_code) == hsa_code)
        if is_update and hsa_id:
            query = query.filter(HSA.hsa_id != hsa_id)
        if query.first():
            errors['hsa_code'] = 'An HSA with this code already exists'
    
    if not hsa_category:
        errors['hsa_category'] = 'HSA Category is required'
    elif hsa_category not in HSA_CATEGORIES:
        errors['hsa_category'] = f'HSA Category must be one of: {", ".join(HSA_CATEGORIES)}'
    
    if not custodian_id:
        errors['custodian_id'] = 'Linked Custodian is required'
    else:
        try:
            custodian_id_int = int(custodian_id)
            custodian = Custodian.query.get(custodian_id_int)
            if not custodian:
                errors['custodian_id'] = 'Invalid custodian selected'
            else:
                existing = HSA.query.filter_by(custodian_id=custodian_id_int).first()
                if existing and (not is_update or existing.hsa_id != hsa_id):
                    errors['custodian_id'] = 'This custodian is already linked to another HSA'
        except ValueError:
            errors['custodian_id'] = 'Invalid custodian ID'
    
    if not status_code:
        errors['status_code'] = 'Status is required'
    elif status_code not in STATUS_CODES:
        errors['status_code'] = 'Status must be A (Active) or I (Inactive)'
    
    return (len(errors) == 0, errors)


@hsa_bp.route('/')
@login_required
@feature_required('custodian_management')
def list_hsa():
    """List all HSAs with filtering and search"""
    current_filter = request.args.get('filter', 'all').strip().lower()
    search_query = request.args.get('search', '').strip()
    
    total_count = HSA.query.count()
    active_count = HSA.query.filter_by(status_code='A').count()
    inactive_count = HSA.query.filter_by(status_code='I').count()
    
    counts = {
        'total': total_count,
        'active': active_count,
        'inactive': inactive_count
    }
    
    query = HSA.query
    
    if current_filter == 'active':
        query = query.filter_by(status_code='A')
    elif current_filter == 'inactive':
        query = query.filter_by(status_code='I')
    
    if search_query:
        search_pattern = f'%{search_query}%'
        query = query.join(Custodian).filter(
            or_(
                HSA.hsa_code.ilike(search_pattern),
                HSA.hsa_category.ilike(search_pattern),
                Custodian.custodian_name.ilike(search_pattern)
            )
        )
    
    hsas = query.order_by(HSA.hsa_code).all()
    
    return render_template(
        'hsa/list.html',
        hsas=hsas,
        counts=counts,
        current_filter=current_filter,
        search_query=search_query,
        hsa_category_labels=HSA_CATEGORY_LABELS
    )


@hsa_bp.route('/create', methods=['GET', 'POST'])
@login_required
@feature_required('custodian_management')
def create_hsa():
    """Create new HSA"""
    if request.method == 'POST':
        is_valid, errors = validate_hsa_data(request.form)
        
        if not is_valid:
            for field, error in errors.items():
                flash(error, 'danger')
            
            custodians = Custodian.query.order_by(Custodian.custodian_name).all()
            return render_template(
                'hsa/create.html',
                custodians=custodians,
                hsa_categories=HSA_CATEGORIES,
                hsa_category_labels=HSA_CATEGORY_LABELS,
                form_data=request.form,
                errors=errors
            )
        
        try:
            from app.security.param_validation import safe_id
            
            hsa = HSA()
            hsa.hsa_code = request.form.get('hsa_code').strip().upper()
            hsa.hsa_category = request.form.get('hsa_category').strip()
            custodian_id = safe_id(request.form.get('custodian_id'))
            if custodian_id <= 0:
                flash('Invalid custodian selected', 'danger')
                return redirect(url_for('hsa.create_hsa'))
            hsa.custodian_id = custodian_id
            hsa.status_code = request.form.get('status_code', 'A').strip()
            hsa.notes = request.form.get('notes', '').strip() or None
            
            add_audit_fields(hsa, current_user, is_new=True)
            
            db.session.add(hsa)
            db.session.commit()
            
            flash(f'HSA "{hsa.hsa_code}" created successfully', 'success')
            return redirect(url_for('hsa.list_hsa', filter='all'))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.exception('Error creating HSA')
            flash('An error occurred while creating the HSA. Please try again or contact support.', 'danger')
            
            custodians = Custodian.query.order_by(Custodian.custodian_name).all()
            return render_template(
                'hsa/create.html',
                custodians=custodians,
                hsa_categories=HSA_CATEGORIES,
                hsa_category_labels=HSA_CATEGORY_LABELS,
                form_data=request.form
            )
    
    custodians = Custodian.query.order_by(Custodian.custodian_name).all()
    return render_template(
        'hsa/create.html',
        custodians=custodians,
        hsa_categories=HSA_CATEGORIES,
        hsa_category_labels=HSA_CATEGORY_LABELS
    )


@hsa_bp.route('/<int:hsa_id>')
@login_required
@feature_required('custodian_management')
def view_hsa(hsa_id):
    """View HSA details"""
    hsa = HSA.query.get_or_404(hsa_id)
    return render_template(
        'hsa/view.html',
        hsa=hsa,
        hsa_category_labels=HSA_CATEGORY_LABELS
    )


@hsa_bp.route('/<int:hsa_id>/edit', methods=['GET', 'POST'])
@login_required
@feature_required('custodian_management')
def edit_hsa(hsa_id):
    """Edit existing HSA"""
    hsa = HSA.query.get_or_404(hsa_id)
    
    if request.method == 'POST':
        submitted_version = request.form.get('version_nbr', type=int)
        if submitted_version != hsa.version_nbr:
            flash('This HSA record was updated by another user. Please reload and try again.', 'warning')
            return redirect(url_for('hsa.view_hsa', hsa_id=hsa_id))
        
        is_valid, errors = validate_hsa_data(request.form, is_update=True, hsa_id=hsa_id)
        
        if not is_valid:
            for field, error in errors.items():
                flash(error, 'danger')
            
            custodians = Custodian.query.order_by(Custodian.custodian_name).all()
            return render_template(
                'hsa/edit.html',
                hsa=hsa,
                custodians=custodians,
                hsa_categories=HSA_CATEGORIES,
                hsa_category_labels=HSA_CATEGORY_LABELS,
                form_data=request.form,
                errors=errors
            )
        
        try:
            from app.security.param_validation import safe_id
            
            hsa.hsa_code = request.form.get('hsa_code').strip().upper()
            hsa.hsa_category = request.form.get('hsa_category').strip()
            custodian_id = safe_id(request.form.get('custodian_id'))
            if custodian_id <= 0:
                flash('Invalid custodian selected', 'danger')
                return redirect(url_for('hsa.edit_hsa', hsa_id=hsa_id))
            hsa.custodian_id = custodian_id
            hsa.status_code = request.form.get('status_code', 'A').strip()
            hsa.notes = request.form.get('notes', '').strip() or None
            
            add_audit_fields(hsa, current_user, is_new=False)
            
            db.session.commit()
            
            flash(f'HSA "{hsa.hsa_code}" updated successfully', 'success')
            return redirect(url_for('hsa.list_hsa', filter='all'))
            
        except StaleDataError:
            db.session.rollback()
            flash('This HSA record was updated by another user. Please reload and try again.', 'warning')
            return redirect(url_for('hsa.view_hsa', hsa_id=hsa_id))
        except Exception as e:
            db.session.rollback()
            current_app.logger.exception('Error updating HSA')
            flash('An error occurred while updating the HSA. Please try again or contact support.', 'danger')
            
            custodians = Custodian.query.order_by(Custodian.custodian_name).all()
            return render_template(
                'hsa/edit.html',
                hsa=hsa,
                custodians=custodians,
                hsa_categories=HSA_CATEGORIES,
                hsa_category_labels=HSA_CATEGORY_LABELS,
                form_data=request.form
            )
    
    custodians = Custodian.query.order_by(Custodian.custodian_name).all()
    return render_template(
        'hsa/edit.html',
        hsa=hsa,
        custodians=custodians,
        hsa_categories=HSA_CATEGORIES,
        hsa_category_labels=HSA_CATEGORY_LABELS
    )


@hsa_bp.route('/<int:hsa_id>/delete', methods=['POST'])
@login_required
@feature_required('custodian_management')
def delete_hsa(hsa_id):
    """Delete HSA with FK reference checks"""
    hsa = HSA.query.get_or_404(hsa_id)
    
    if hsa.beneficiaries and len(hsa.beneficiaries) > 0:
        flash('This HSA cannot be deleted because it has registered beneficiaries.', 'danger')
        return redirect(url_for('hsa.view_hsa', hsa_id=hsa_id))
    
    try:
        hsa_code = hsa.hsa_code
        db.session.delete(hsa)
        db.session.commit()
        
        flash(f'HSA "{hsa_code}" deleted successfully', 'success')
        return redirect(url_for('hsa.list_hsa'))
        
    except IntegrityError:
        db.session.rollback()
        flash('This HSA cannot be deleted because it is referenced by other records.', 'danger')
        return redirect(url_for('hsa.view_hsa', hsa_id=hsa_id))
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception('Error deleting HSA')
        flash('An error occurred while deleting the HSA. Please try again or contact support.', 'danger')
        return redirect(url_for('hsa.view_hsa', hsa_id=hsa_id))
