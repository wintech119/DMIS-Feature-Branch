"""
Dashboard Blueprint - Role-Based Dashboards with Modern UI

Provides role-specific dashboard views matching the Relief Package preparation
UI/UX standards with summary cards, filter tabs, and modern styling.
"""

from flask import Blueprint, render_template, request, flash, abort
from flask_login import login_required, current_user
from sqlalchemy import func, desc, or_, and_, extract
from app.db.models import (
    db, Inventory, Item, ItemCategory, Warehouse, 
    Event, Donor, Agency, User, ReliefRqst, ReliefRequestFulfillmentLock, ReliefPkg, ReliefPkgItem,
    Donation, DonationItem, Country
)
from app.services import relief_request_service as rr_service
from app.services.dashboard_service import DashboardService
from app.core.feature_registry import FeatureRegistry
from app.core.rbac import has_role, role_required
from datetime import datetime, timedelta
from collections import defaultdict
from app.utils.timezone import now as jamaica_now

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
@login_required
def index():
    """
    Main dashboard with role-based routing.
    Routes users to role-specific dashboards with modern UI.
    """
    primary_role = FeatureRegistry.get_primary_role(current_user)
    
    # Route to role-specific dashboards
    if primary_role == 'SYSTEM_ADMINISTRATOR':
        return admin_dashboard()
    elif primary_role in ['ODPEM_DG', 'ODPEM_DDG', 'ODPEM_DIR_PEOD']:
        # Route executive roles to Director Dashboard
        from flask import redirect, url_for
        return redirect(url_for('director.dashboard'))
    elif primary_role in ['LOGISTICS_MANAGER', 'LOGISTICS_OFFICER']:
        # Route logistics roles to general dashboard
        return general_dashboard()
    elif primary_role in ['AGENCY_DISTRIBUTOR', 'AGENCY_SHELTER']:
        return agency_dashboard()
    elif primary_role == 'INVENTORY_CLERK':
        return inventory_dashboard()
    else:
        # Default dashboard for unrecognized roles
        return general_dashboard()


@dashboard_bp.route('/agency')
@login_required
def agency_dashboard():
    """
    Agency dashboard for relief agencies.
    Shows agency's relief requests with modern UI.
    """
    # Get dashboard data from service
    dashboard_data = DashboardService.get_dashboard_data(current_user)
    
    # Get filter parameter
    current_filter = request.args.get('filter', 'active')
    
    # Query agency's requests
    from sqlalchemy.orm import joinedload
    
    base_query = ReliefRqst.query.options(
        joinedload(ReliefRqst.items),
        joinedload(ReliefRqst.status),
        joinedload(ReliefRqst.eligible_event)
    ).filter_by(agency_id=current_user.agency_id)
    
    # Apply filters
    if current_filter == 'draft':
        requests = base_query.filter_by(status_code=0).order_by(desc(ReliefRqst.create_dtime)).all()
    elif current_filter == 'pending':
        requests = base_query.filter_by(status_code=1).order_by(desc(ReliefRqst.request_date)).all()
    elif current_filter == 'approved':
        requests = base_query.filter(
            ReliefRqst.status_code.in_([3, 5])
        ).order_by(desc(ReliefRqst.review_dtime)).all()
    elif current_filter == 'completed':
        requests = base_query.filter_by(status_code=7).order_by(desc(ReliefRqst.action_dtime)).all()
    else:  # 'active' - default
        requests = base_query.filter(
            ReliefRqst.status_code.in_([0, 1, 3, 5])
        ).order_by(desc(ReliefRqst.create_dtime)).all()
    
    # Calculate counts
    global_counts = {
        'draft': base_query.filter_by(status_code=0).count(),
        'pending': base_query.filter_by(status_code=1).count(),
        'approved': base_query.filter(ReliefRqst.status_code.in_([3, 5])).count(),
        'completed': base_query.filter_by(status_code=7).count(),
    }
    global_counts['active'] = global_counts['draft'] + global_counts['pending'] + global_counts['approved']
    
    context = {
        **dashboard_data,
        'requests': requests,
        'current_filter': current_filter,
        'global_counts': global_counts,
        'counts': global_counts,
    }
    
    return render_template('dashboard/agency.html', **context)


@dashboard_bp.route('/director')
@login_required
def director_dashboard():
    """
    Director dashboard for ODPEM executives.
    Shows eligibility review queue with modern UI.
    """
    # Get dashboard data from service
    dashboard_data = DashboardService.get_dashboard_data(current_user)
    
    # Get filter parameter
    current_filter = request.args.get('filter', 'pending')
    
    # Query requests
    from sqlalchemy.orm import joinedload
    
    base_query = ReliefRqst.query.options(
        joinedload(ReliefRqst.agency),
        joinedload(ReliefRqst.items),
        joinedload(ReliefRqst.status),
        joinedload(ReliefRqst.eligible_event)
    )
    
    # Apply filters
    if current_filter == 'pending':
        requests = base_query.filter_by(status_code=1).order_by(desc(ReliefRqst.request_date)).all()
    elif current_filter == 'approved':
        requests = base_query.filter_by(status_code=3).order_by(desc(ReliefRqst.review_dtime)).all()
    elif current_filter == 'in_progress':
        requests = base_query.filter(
            ReliefRqst.status_code.in_([1, 3, 5])
        ).order_by(desc(ReliefRqst.request_date)).all()
    elif current_filter == 'completed':
        requests = base_query.filter_by(status_code=7).order_by(desc(ReliefRqst.action_dtime)).all()
    else:  # 'all'
        requests = base_query.order_by(desc(ReliefRqst.request_date)).all()
    
    # Calculate counts
    global_counts = {
        'pending': base_query.filter_by(status_code=1).count(),
        'approved': base_query.filter_by(status_code=3).count(),
        'in_progress': base_query.filter(ReliefRqst.status_code.in_([1, 3, 5])).count(),
        'completed': base_query.filter_by(status_code=7).count(),
    }
    global_counts['all'] = base_query.count()
    
    context = {
        **dashboard_data,
        'requests': requests,
        'current_filter': current_filter,
        'global_counts': global_counts,
        'counts': global_counts,
    }
    
    return render_template('dashboard/director.html', **context)


@dashboard_bp.route('/admin')
@login_required
def admin_dashboard():
    """
    System administrator dashboard with system-wide metrics.
    """
    dashboard_data = DashboardService.get_dashboard_data(current_user)
    
    # System metrics
    total_users = User.query.count()
    total_agencies = Agency.query.filter_by(status_code='A').count()
    total_warehouses = Warehouse.query.filter_by(status_code='A').count()
    total_items = Item.query.filter_by(status_code='A').count()
    total_events = Event.query.filter_by(status_code='A').count()
    
    # Recent activity
    recent_requests = ReliefRqst.query.order_by(desc(ReliefRqst.create_dtime)).limit(10).all()
    recent_users = User.query.order_by(desc(User.create_dtime)).limit(5).all()
    
    context = {
        **dashboard_data,
        'total_users': total_users,
        'total_agencies': total_agencies,
        'total_warehouses': total_warehouses,
        'total_items': total_items,
        'total_events': total_events,
        'recent_requests': recent_requests,
        'recent_users': recent_users,
    }
    
    return render_template('dashboard/admin.html', **context)


@dashboard_bp.route('/inventory')
@login_required
def inventory_dashboard():
    """
    Inventory clerk dashboard focused on stock management.
    """
    dashboard_data = DashboardService.get_dashboard_data(current_user)
    
    # Inventory metrics
    low_stock_items = db.session.query(
        Item.item_id, 
        Item.item_name,
        func.sum(Inventory.usable_qty).label('total_qty'),
        Item.reorder_qty
    ).join(Inventory).filter(
        Item.status_code == 'A'
    ).group_by(
        Item.item_id, Item.item_name, Item.reorder_qty
    ).having(
        func.sum(Inventory.usable_qty) <= Item.reorder_qty
    ).limit(10).all()
    
    context = {
        **dashboard_data,
        'low_stock_items': low_stock_items,
    }
    
    return render_template('dashboard/inventory.html', **context)


@dashboard_bp.route('/general')
@login_required
def general_dashboard():
    """
    General dashboard for users without specific role dashboards.
    """
    dashboard_data = DashboardService.get_dashboard_data(current_user)
    
    context = {
        **dashboard_data,
    }
    
    return render_template('dashboard/general.html', **context)


@dashboard_bp.route('/donations-analytics')
@login_required
@role_required('ODPEM_DG', 'ODPEM_DDG', 'ODPEM_DIR_PEOD', 'LOGISTICS_MANAGER')
def donations_analytics():
    """
    Donations Analytics Dashboard - Executive view of donation metrics and trends.
    
    Access: DG, Deputy DG, Director PEOD, Logistics Manager
    
    Displays:
    - KPIs: Total donations, total value, unique donors, countries
    - Charts: Donations by donor, by country, over time, distribution
    """
    now = jamaica_now()
    
    # ========== KPI METRICS ==========
    
    # Total donations count
    total_donations = Donation.query.count()
    
    # Total donation value (sum of tot_item_cost)
    total_value = db.session.query(
        func.coalesce(func.sum(Donation.tot_item_cost), 0)
    ).scalar() or 0
    
    # Total donation value by type (GOODS vs FUNDS)
    total_value_goods = db.session.query(
        func.coalesce(func.sum(DonationItem.item_cost), 0)
    ).filter(
        DonationItem.donation_type == 'GOODS'
    ).scalar() or 0
    
    total_value_funds = db.session.query(
        func.coalesce(func.sum(DonationItem.item_cost), 0)
    ).filter(
        DonationItem.donation_type == 'FUNDS'
    ).scalar() or 0
    
    # Unique donors count
    unique_donors = db.session.query(
        func.count(func.distinct(Donation.donor_id))
    ).scalar() or 0
    
    # Number of countries donations came from
    countries_count = db.session.query(
        func.count(func.distinct(Donation.origin_country_id))
    ).scalar() or 0
    
    # ========== DONATIONS BY DONOR (Top 10) ==========
    
    donations_by_donor = db.session.query(
        Donor.donor_name,
        func.sum(Donation.tot_item_cost).label('total_amount'),
        func.count(Donation.donation_id).label('donation_count')
    ).join(
        Donation, Donor.donor_id == Donation.donor_id
    ).group_by(
        Donor.donor_id, Donor.donor_name
    ).order_by(
        desc('total_amount')
    ).limit(10).all()
    
    donor_chart_data = {
        'labels': [d.donor_name[:30] + '...' if len(d.donor_name) > 30 else d.donor_name for d in donations_by_donor],
        'amounts': [float(d.total_amount) for d in donations_by_donor],
        'counts': [d.donation_count for d in donations_by_donor]
    }
    
    # ========== DONATIONS BY COUNTRY ==========
    
    donations_by_country = db.session.query(
        Country.country_name,
        func.sum(Donation.tot_item_cost).label('total_amount'),
        func.count(Donation.donation_id).label('donation_count')
    ).join(
        Donation, Country.country_id == Donation.origin_country_id
    ).group_by(
        Country.country_id, Country.country_name
    ).order_by(
        desc('total_amount')
    ).limit(10).all()
    
    country_chart_data = {
        'labels': [c.country_name for c in donations_by_country],
        'amounts': [float(c.total_amount) for c in donations_by_country],
        'counts': [c.donation_count for c in donations_by_country]
    }
    
    # ========== DONATIONS OVER TIME (Last 12 months) ==========
    
    twelve_months_ago = now - timedelta(days=365)
    
    donations_over_time = db.session.query(
        extract('year', Donation.received_date).label('year'),
        extract('month', Donation.received_date).label('month'),
        func.sum(Donation.tot_item_cost).label('total_amount'),
        func.count(Donation.donation_id).label('donation_count')
    ).filter(
        Donation.received_date >= twelve_months_ago.date()
    ).group_by(
        extract('year', Donation.received_date),
        extract('month', Donation.received_date)
    ).order_by(
        'year', 'month'
    ).all()
    
    # Format month labels and data
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    
    timeline_data = {
        'labels': [],
        'amounts': [],
        'counts': []
    }
    
    for row in donations_over_time:
        month_label = f"{month_names[int(row.month) - 1]} {int(row.year)}"
        timeline_data['labels'].append(month_label)
        timeline_data['amounts'].append(float(row.total_amount))
        timeline_data['counts'].append(row.donation_count)
    
    # ========== DONATIONS BY STATUS ==========
    
    donations_by_status = db.session.query(
        Donation.status_code,
        func.count(Donation.donation_id).label('count'),
        func.sum(Donation.tot_item_cost).label('total_amount')
    ).group_by(
        Donation.status_code
    ).all()
    
    status_labels_map = {
        'E': 'Entered',
        'V': 'Verified',
        'P': 'Processed'
    }
    
    status_chart_data = {
        'labels': [status_labels_map.get(s.status_code, s.status_code) for s in donations_by_status],
        'counts': [s.count for s in donations_by_status],
        'amounts': [float(s.total_amount) if s.total_amount else 0 for s in donations_by_status]
    }
    
    # ========== DONATIONS BY EVENT (Distribution) ==========
    
    donations_by_event = db.session.query(
        Event.event_name,
        func.sum(Donation.tot_item_cost).label('total_amount'),
        func.count(Donation.donation_id).label('donation_count')
    ).join(
        Donation, Event.event_id == Donation.event_id
    ).group_by(
        Event.event_id, Event.event_name
    ).order_by(
        desc('total_amount')
    ).limit(10).all()
    
    event_chart_data = {
        'labels': [e.event_name[:25] + '...' if len(e.event_name) > 25 else e.event_name for e in donations_by_event],
        'amounts': [float(e.total_amount) for e in donations_by_event],
        'counts': [e.donation_count for e in donations_by_event]
    }
    
    # ========== RECENT DONATIONS ==========
    
    recent_donations = Donation.query.options(
        db.joinedload(Donation.donor),
        db.joinedload(Donation.origin_country),
        db.joinedload(Donation.event)
    ).order_by(
        desc(Donation.received_date)
    ).limit(5).all()
    
    context = {
        # KPIs
        'total_donations': total_donations,
        'total_value': float(total_value),
        'total_value_goods': float(total_value_goods),
        'total_value_funds': float(total_value_funds),
        'unique_donors': unique_donors,
        'countries_count': countries_count,
        
        # Chart data
        'donor_chart_data': donor_chart_data,
        'country_chart_data': country_chart_data,
        'timeline_data': timeline_data,
        'status_chart_data': status_chart_data,
        'event_chart_data': event_chart_data,
        
        # Recent donations
        'recent_donations': recent_donations,
        
        # Status labels
        'status_labels_map': status_labels_map
    }
    
    return render_template('dashboard/donations_analytics.html', **context)


@dashboard_bp.route('/relief-package-analytics')
@login_required
@role_required('ODPEM_DG', 'ODPEM_DDG', 'ODPEM_DIR_PEOD', 'LOGISTICS_MANAGER')
def relief_package_analytics():
    """
    Relief Package Analytics Dashboard - Executive view of dispatched relief packages.
    
    Access: DG, Deputy DG, Director PEOD, Logistics Manager
    
    Displays:
    - KPIs: Total packages dispatched, total items, beneficiary locations, requests fulfilled
    - Charts: By destination type, by parish, over time, top destinations
    - Detail table: Drill-down of dispatched packages
    """
    from app.db.models import ReliefPkg, ReliefPkgItem, ReliefRqst, Agency, Parish, Item
    from sqlalchemy.orm import joinedload
    
    now = jamaica_now()
    
    dispatched_statuses = ['D', 'R']
    
    base_query = ReliefPkg.query.filter(
        ReliefPkg.status_code.in_(dispatched_statuses)
    )
    
    total_packages = base_query.count()
    
    total_items = db.session.query(
        func.coalesce(func.sum(ReliefPkgItem.item_qty), 0)
    ).join(
        ReliefPkg, ReliefPkgItem.reliefpkg_id == ReliefPkg.reliefpkg_id
    ).filter(
        ReliefPkg.status_code.in_(dispatched_statuses)
    ).scalar() or 0
    
    beneficiary_locations = db.session.query(
        func.count(func.distinct(ReliefPkg.agency_id))
    ).filter(
        ReliefPkg.status_code.in_(dispatched_statuses)
    ).scalar() or 0
    
    requests_fulfilled = db.session.query(
        func.count(func.distinct(ReliefPkg.reliefrqst_id))
    ).filter(
        ReliefPkg.status_code.in_(dispatched_statuses)
    ).scalar() or 0
    
    packages_by_type = db.session.query(
        Agency.agency_type,
        func.count(ReliefPkg.reliefpkg_id).label('package_count'),
        func.coalesce(func.sum(ReliefPkgItem.item_qty), 0).label('total_items')
    ).join(
        ReliefPkg, Agency.agency_id == ReliefPkg.agency_id
    ).outerjoin(
        ReliefPkgItem, ReliefPkg.reliefpkg_id == ReliefPkgItem.reliefpkg_id
    ).filter(
        ReliefPkg.status_code.in_(dispatched_statuses)
    ).group_by(
        Agency.agency_type
    ).all()
    
    type_labels_map = {
        'SHELTER': 'Shelters',
        'DISTRIBUTOR': 'Distributors',
        'OTHER': 'Other'
    }
    
    destination_type_data = {
        'labels': [type_labels_map.get(t.agency_type, t.agency_type or 'Unknown') for t in packages_by_type],
        'counts': [t.package_count for t in packages_by_type],
        'items': [float(t.total_items) for t in packages_by_type]
    }
    
    packages_by_parish = db.session.query(
        Parish.parish_name,
        func.count(ReliefPkg.reliefpkg_id).label('package_count')
    ).join(
        Agency, Parish.parish_code == Agency.parish_code
    ).join(
        ReliefPkg, Agency.agency_id == ReliefPkg.agency_id
    ).filter(
        ReliefPkg.status_code.in_(dispatched_statuses)
    ).group_by(
        Parish.parish_code, Parish.parish_name
    ).order_by(
        desc('package_count')
    ).all()
    
    parish_chart_data = {
        'labels': [p.parish_name for p in packages_by_parish],
        'counts': [p.package_count for p in packages_by_parish]
    }
    
    twelve_months_ago = now - timedelta(days=365)
    
    packages_over_time = db.session.query(
        extract('year', ReliefPkg.dispatch_dtime).label('year'),
        extract('month', ReliefPkg.dispatch_dtime).label('month'),
        func.count(ReliefPkg.reliefpkg_id).label('package_count')
    ).filter(
        ReliefPkg.status_code.in_(dispatched_statuses),
        ReliefPkg.dispatch_dtime.isnot(None),
        ReliefPkg.dispatch_dtime >= twelve_months_ago
    ).group_by(
        extract('year', ReliefPkg.dispatch_dtime),
        extract('month', ReliefPkg.dispatch_dtime)
    ).order_by(
        'year', 'month'
    ).all()
    
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    
    timeline_data = {
        'labels': [],
        'counts': []
    }
    
    for row in packages_over_time:
        month_label = f"{month_names[int(row.month) - 1]} {int(row.year)}"
        timeline_data['labels'].append(month_label)
        timeline_data['counts'].append(row.package_count)
    
    top_destinations = db.session.query(
        Agency.agency_name,
        Agency.agency_type,
        func.count(ReliefPkg.reliefpkg_id).label('package_count'),
        func.coalesce(func.sum(ReliefPkgItem.item_qty), 0).label('total_items')
    ).join(
        ReliefPkg, Agency.agency_id == ReliefPkg.agency_id
    ).outerjoin(
        ReliefPkgItem, ReliefPkg.reliefpkg_id == ReliefPkgItem.reliefpkg_id
    ).filter(
        ReliefPkg.status_code.in_(dispatched_statuses)
    ).group_by(
        Agency.agency_id, Agency.agency_name, Agency.agency_type
    ).order_by(
        desc('package_count')
    ).limit(10).all()
    
    top_destinations_data = {
        'labels': [d.agency_name[:35] + '...' if len(d.agency_name) > 35 else d.agency_name for d in top_destinations],
        'counts': [d.package_count for d in top_destinations],
        'items': [float(d.total_items) for d in top_destinations],
        'types': [type_labels_map.get(d.agency_type, d.agency_type or 'Unknown') for d in top_destinations]
    }
    
    dispatched_packages = ReliefPkg.query.options(
        joinedload(ReliefPkg.agency).joinedload(Agency.parish),
        joinedload(ReliefPkg.relief_request)
    ).filter(
        ReliefPkg.status_code.in_(dispatched_statuses)
    ).order_by(
        desc(ReliefPkg.dispatch_dtime)
    ).limit(100).all()
    
    package_item_counts = {}
    if dispatched_packages:
        pkg_ids = [pkg.reliefpkg_id for pkg in dispatched_packages]
        item_counts = db.session.query(
            ReliefPkgItem.reliefpkg_id,
            func.sum(ReliefPkgItem.item_qty).label('total_qty')
        ).filter(
            ReliefPkgItem.reliefpkg_id.in_(pkg_ids)
        ).group_by(
            ReliefPkgItem.reliefpkg_id
        ).all()
        package_item_counts = {ic.reliefpkg_id: float(ic.total_qty) for ic in item_counts}
    
    status_labels = {
        'D': 'Dispatched',
        'R': 'Received'
    }
    
    context = {
        'total_packages': total_packages,
        'total_items': int(total_items),
        'beneficiary_locations': beneficiary_locations,
        'requests_fulfilled': requests_fulfilled,
        
        'destination_type_data': destination_type_data,
        'parish_chart_data': parish_chart_data,
        'timeline_data': timeline_data,
        'top_destinations_data': top_destinations_data,
        
        'dispatched_packages': dispatched_packages,
        'package_item_counts': package_item_counts,
        'status_labels': status_labels,
        'type_labels_map': type_labels_map
    }
    
    return render_template('dashboard/relief_package_analytics.html', **context)


@dashboard_bp.route('/aid-movement')
@login_required
@role_required('ODPEM_DG', 'ODPEM_DDG', 'ODPEM_DIR_PEOD', 'LOGISTICS_MANAGER')
def aid_movement_dashboard():
    """
    Aid Movement Dashboard - Read-only analytics on aid received, issued, and in store.
    
    Access: DG, Deputy DG, Director PEOD, Logistics Manager
    
    Displays:
    - KPIs: Total Received, Total Issued, In Store
    - Filters: Item search, warehouse selection, date range
    - Table: Aid movement transactions
    """
    from sqlalchemy import text
    
    warehouse_id = request.args.get('warehouse_id', '')
    item_search = request.args.get('item_search', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    movement_type = request.args.get('movement_type', '')
    data_source = request.args.get('data_source', '')
    page = request.args.get('page', 1, type=int)
    per_page = 25
    
    warehouses = Warehouse.query.filter_by(status_code='A').order_by(Warehouse.warehouse_name).all()
    
    base_conditions = []
    params = {}
    
    if warehouse_id:
        base_conditions.append("t.warehouse_id = :warehouse_id")
        params['warehouse_id'] = int(warehouse_id)
    
    if item_search:
        base_conditions.append("LOWER(i.item_name) LIKE :item_search")
        params['item_search'] = f'%{item_search.lower()}%'
    
    if date_from:
        base_conditions.append("t.created_at >= :date_from")
        params['date_from'] = date_from
    
    if date_to:
        base_conditions.append("t.created_at <= (:date_to)::date + interval '1 day'")
        params['date_to'] = date_to
    
    if movement_type:
        base_conditions.append("t.ttype = :movement_type")
        params['movement_type'] = movement_type
    
    if data_source == 'JDF':
        base_conditions.append("t.created_by IN ('HADR_IMPORT', 'IMPORT')")
    elif data_source == 'MLSS':
        base_conditions.append("t.created_by = 'MLSS_IMPORT'")
    
    where_clause = "WHERE " + " AND ".join(base_conditions) if base_conditions else ""
    
    kpi_sql = text(f"""
        SELECT 
            COALESCE(SUM(CASE WHEN t.ttype = 'R' THEN t.qty ELSE 0 END), 0) as total_received,
            COALESCE(SUM(CASE WHEN t.ttype = 'I' THEN t.qty ELSE 0 END), 0) as total_issued
        FROM transaction t
        LEFT JOIN item i ON t.item_id = i.item_id
        {where_clause}
    """)
    
    kpi_result = db.session.execute(kpi_sql, params).fetchone()
    total_received = float(kpi_result.total_received)
    total_issued = float(kpi_result.total_issued)
    in_store = total_received - total_issued
    
    count_sql = text(f"""
        SELECT COUNT(*) as total
        FROM transaction t
        LEFT JOIN item i ON t.item_id = i.item_id
        {where_clause}
    """)
    total_count = db.session.execute(count_sql, params).scalar() or 0
    total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1
    
    offset = (page - 1) * per_page
    transactions_sql = text(f"""
        SELECT 
            t.id,
            t.ttype,
            t.qty,
            t.created_at,
            t.notes,
            i.item_name,
            i.item_desc,
            w.warehouse_name,
            w.warehouse_type,
            c.category_desc,
            u.uom_desc
        FROM transaction t
        LEFT JOIN item i ON t.item_id = i.item_id
        LEFT JOIN warehouse w ON t.warehouse_id = w.warehouse_id
        LEFT JOIN itemcatg c ON i.category_id = c.category_id
        LEFT JOIN unitofmeasure u ON i.default_uom_code = u.uom_code
        {where_clause}
        ORDER BY t.created_at DESC
        LIMIT :limit OFFSET :offset
    """)
    
    query_params = {**params, 'limit': per_page, 'offset': offset}
    transactions = db.session.execute(transactions_sql, query_params).fetchall()
    
    pagination = {
        'page': page,
        'per_page': per_page,
        'total': total_count,
        'pages': total_pages,
        'has_prev': page > 1,
        'has_next': page < total_pages,
        'prev_num': page - 1 if page > 1 else None,
        'next_num': page + 1 if page < total_pages else None,
    }
    
    def iter_pages(left_edge=2, left_current=2, right_current=3, right_edge=2):
        last = 0
        for num in range(1, total_pages + 1):
            if num <= left_edge or \
               (num > page - left_current - 1 and num < page + right_current) or \
               num > total_pages - right_edge:
                if last + 1 != num:
                    yield None
                yield num
                last = num
    
    pagination['iter_pages'] = iter_pages
    
    filters = {
        'warehouse_id': warehouse_id,
        'item_search': item_search,
        'date_from': date_from,
        'date_to': date_to,
        'movement_type': movement_type,
        'data_source': data_source
    }
    
    context = {
        'total_received': total_received,
        'total_issued': total_issued,
        'in_store': in_store,
        'transactions': transactions,
        'warehouses': warehouses,
        'filters': filters,
        'pagination': pagination
    }
    
    return render_template('dashboard/aid_movement_dashboard.html', **context)


@dashboard_bp.route('/aid-movement/item-detail')
@login_required
@role_required('ODPEM_DG', 'ODPEM_DDG', 'ODPEM_DIR_PEOD', 'LOGISTICS_MANAGER')
def aid_item_movement_detail():
    """
    Item Distribution Dashboard - Drill-down view for a specific item's movements.
    
    Access: DG, Deputy DG, Director PEOD, Logistics Manager
    
    Displays:
    - Filters: Category, Item selection (required), warehouse, movement type, date range
    - Summary Cards: Total Received, Total Issued, In Store (for selected item)
    - Detail Table: Per-warehouse breakdown for the selected item
    """
    from sqlalchemy import text
    
    category_id = request.args.get('category_id', '')
    item_id = request.args.get('item_id', '')
    warehouse_id = request.args.get('warehouse_id', '')
    movement_type = request.args.get('movement_type', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    data_source = request.args.get('data_source', '')
    
    categories = ItemCategory.query.filter_by(status_code='A').order_by(ItemCategory.category_desc).all()
    items = Item.query.filter_by(status_code='A').order_by(Item.item_name).all()
    warehouses = Warehouse.query.filter_by(status_code='A').order_by(Warehouse.warehouse_name).all()
    
    summary_totals = {
        'total_received': 0,
        'total_issued': 0,
        'in_store': 0
    }
    detail_rows = []
    selected_item = None
    selected_category = None
    selected_warehouse = None
    movement_type_label = None
    data_source_label = None
    has_filter = item_id or category_id or warehouse_id or movement_type or start_date or end_date or data_source
    
    if has_filter:
        if item_id:
            selected_item = Item.query.get(int(item_id))
        if category_id:
            selected_category = ItemCategory.query.get(int(category_id))

        if warehouse_id:
            selected_warehouse = next((w for w in warehouses if str(w.warehouse_id) == warehouse_id), None)

        if movement_type:
            movement_type_label = {
                'R': 'Received Only',
                'I': 'Issued Only'
            }.get(movement_type, 'Received & Issued')
        
        if data_source:
            data_source_label = {
                'JDF': 'JDF',
                'MLSS': 'MLSS'
            }.get(data_source, 'All Sources')
        
        base_conditions = []
        params = {}
        
        if item_id:
            base_conditions.append("t.item_id = :item_id")
            params['item_id'] = int(item_id)
        elif category_id:
            base_conditions.append("i.category_id = :category_id")
            params['category_id'] = int(category_id)
        
        if warehouse_id:
            base_conditions.append("t.warehouse_id = :warehouse_id")
            params['warehouse_id'] = int(warehouse_id)
        
        if movement_type:
            base_conditions.append("t.ttype = :movement_type")
            params['movement_type'] = movement_type
        
        if start_date:
            base_conditions.append("t.created_at >= :start_date")
            params['start_date'] = start_date
        
        if end_date:
            base_conditions.append("t.created_at <= (:end_date)::date + interval '1 day'")
            params['end_date'] = end_date
        
        if data_source == 'JDF':
            base_conditions.append("t.created_by IN ('HADR_IMPORT', 'IMPORT')")
        elif data_source == 'MLSS':
            base_conditions.append("t.created_by = 'MLSS_IMPORT'")
        
        where_clause = "WHERE " + " AND ".join(base_conditions) if base_conditions else ""
        
        summary_sql = text(f"""
            SELECT 
                COALESCE(SUM(CASE WHEN t.ttype = 'R' THEN t.qty ELSE 0 END), 0) as total_received,
                COALESCE(SUM(CASE WHEN t.ttype = 'I' THEN t.qty ELSE 0 END), 0) as total_issued
            FROM transaction t
            JOIN item i ON i.item_id = t.item_id
            {where_clause}
        """)
        
        summary_result = db.session.execute(summary_sql, params).fetchone()
        summary_totals['total_received'] = float(summary_result.total_received)
        summary_totals['total_issued'] = float(summary_result.total_issued)
        summary_totals['in_store'] = summary_totals['total_received'] - summary_totals['total_issued']
        
        detail_sql = text(f"""
            SELECT 
                w.warehouse_id,
                w.warehouse_name,
                w.warehouse_type,
                COALESCE(SUM(CASE WHEN t.ttype = 'R' THEN t.qty ELSE 0 END), 0) as total_received,
                COALESCE(SUM(CASE WHEN t.ttype = 'I' THEN t.qty ELSE 0 END), 0) as total_issued,
                COALESCE(SUM(CASE WHEN t.ttype = 'R' THEN t.qty ELSE 0 END), 0) 
                - COALESCE(SUM(CASE WHEN t.ttype = 'I' THEN t.qty ELSE 0 END), 0) as in_store
            FROM transaction t
            JOIN item i ON i.item_id = t.item_id
            JOIN warehouse w ON w.warehouse_id = t.warehouse_id
            {where_clause}
            GROUP BY w.warehouse_id, w.warehouse_name, w.warehouse_type
            ORDER BY w.warehouse_name
        """)
        
        detail_results = db.session.execute(detail_sql, params).fetchall()
        detail_rows = [
            {
                'warehouse_id': row.warehouse_id,
                'warehouse_name': row.warehouse_name,
                'warehouse_type': row.warehouse_type,
                'total_received': float(row.total_received),
                'total_issued': float(row.total_issued),
                'in_store': float(row.in_store)
            }
            for row in detail_results
        ]
    
    filters = {
        'category_id': category_id,
        'item_id': item_id,
        'warehouse_id': warehouse_id,
        'movement_type': movement_type,
        'start_date': start_date,
        'end_date': end_date,
        'data_source': data_source
    }
    
    category_chart_data = {'labels': [], 'received': [], 'issued': [], 'in_store': []}
    warehouse_chart_data = {'labels': [], 'received': [], 'issued': [], 'in_store': []}
    
    chart_conditions = []
    chart_params = {}
    
    if warehouse_id:
        chart_conditions.append("t.warehouse_id = :warehouse_id")
        chart_params['warehouse_id'] = int(warehouse_id)
    
    if movement_type:
        chart_conditions.append("t.ttype = :movement_type")
        chart_params['movement_type'] = movement_type
    
    if start_date:
        chart_conditions.append("t.created_at >= :start_date")
        chart_params['start_date'] = start_date
    
    if end_date:
        chart_conditions.append("t.created_at <= (:end_date)::date + interval '1 day'")
        chart_params['end_date'] = end_date
    
    if category_id:
        chart_conditions.append("i.category_id = :category_id")
        chart_params['category_id'] = int(category_id)
    
    if item_id:
        chart_conditions.append("t.item_id = :item_id")
        chart_params['item_id'] = int(item_id)
    
    if data_source == 'JDF':
        chart_conditions.append("t.created_by IN ('HADR_IMPORT', 'IMPORT')")
    elif data_source == 'MLSS':
        chart_conditions.append("t.created_by = 'MLSS_IMPORT'")
    
    chart_where_clause = "WHERE " + " AND ".join(chart_conditions) if chart_conditions else ""
    
    category_sql = text(f"""
        SELECT 
            ic.category_id,
            ic.category_desc,
            COALESCE(SUM(CASE WHEN t.ttype = 'R' THEN t.qty ELSE 0 END), 0) as total_received,
            COALESCE(SUM(CASE WHEN t.ttype = 'I' THEN t.qty ELSE 0 END), 0) as total_issued,
            COALESCE(SUM(CASE WHEN t.ttype = 'R' THEN t.qty ELSE 0 END), 0) 
            - COALESCE(SUM(CASE WHEN t.ttype = 'I' THEN t.qty ELSE 0 END), 0) as in_store
        FROM transaction t
        JOIN item i ON i.item_id = t.item_id
        JOIN itemcatg ic ON ic.category_id = i.category_id
        {chart_where_clause}
        GROUP BY ic.category_id, ic.category_desc
        HAVING COALESCE(SUM(CASE WHEN t.ttype = 'R' THEN t.qty ELSE 0 END), 0) > 0
            OR COALESCE(SUM(CASE WHEN t.ttype = 'I' THEN t.qty ELSE 0 END), 0) > 0
        ORDER BY total_received DESC
        LIMIT 10
    """)
    
    category_results = db.session.execute(category_sql, chart_params).fetchall()
    for row in category_results:
        category_chart_data['labels'].append(row.category_desc)
        category_chart_data['received'].append(float(row.total_received))
        category_chart_data['issued'].append(float(row.total_issued))
        category_chart_data['in_store'].append(float(row.in_store))
    
    warehouse_sql = text(f"""
        SELECT 
            w.warehouse_id,
            w.warehouse_name,
            COALESCE(SUM(CASE WHEN t.ttype = 'R' THEN t.qty ELSE 0 END), 0) as total_received,
            COALESCE(SUM(CASE WHEN t.ttype = 'I' THEN t.qty ELSE 0 END), 0) as total_issued,
            COALESCE(SUM(CASE WHEN t.ttype = 'R' THEN t.qty ELSE 0 END), 0) 
            - COALESCE(SUM(CASE WHEN t.ttype = 'I' THEN t.qty ELSE 0 END), 0) as in_store
        FROM transaction t
        JOIN item i ON i.item_id = t.item_id
        JOIN warehouse w ON w.warehouse_id = t.warehouse_id
        {chart_where_clause}
        GROUP BY w.warehouse_id, w.warehouse_name
        HAVING COALESCE(SUM(CASE WHEN t.ttype = 'R' THEN t.qty ELSE 0 END), 0) > 0
            OR COALESCE(SUM(CASE WHEN t.ttype = 'I' THEN t.qty ELSE 0 END), 0) > 0
        ORDER BY total_received DESC
    """)
    
    warehouse_results = db.session.execute(warehouse_sql, chart_params).fetchall()
    for row in warehouse_results:
        warehouse_chart_data['labels'].append(row.warehouse_name)
        warehouse_chart_data['received'].append(float(row.total_received))
        warehouse_chart_data['issued'].append(float(row.total_issued))
        warehouse_chart_data['in_store'].append(float(row.in_store))
    
    context = {
        'categories': categories,
        'items': items,
        'warehouses': warehouses,
        'selected_item': selected_item,
        'selected_category': selected_category,
        'selected_warehouse': selected_warehouse,
        'movement_type_label': movement_type_label,
        'data_source_label': data_source_label,
        'has_filter': has_filter,
        'summary_totals': summary_totals,
        'detail_rows': detail_rows,
        'filters': filters,
        'category_chart_data': category_chart_data,
        'warehouse_chart_data': warehouse_chart_data
    }
    
    return render_template('dashboard/aid_item_movement_detail.html', **context)
