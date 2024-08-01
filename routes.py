from flask import render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.utils import secure_filename
from models import User, Customer, Professional, db, Service
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps
from main import app
import os
import seaborn as sns
from datetime import datetime
import matplotlib.pyplot as plt
import io
import base64
from sqlalchemy import func

def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        user_id = session.get('user_id', None)
        if not user_id:
            flash("Please login to continue!")
            return redirect(url_for('login'))
        return func(*args, **kwargs)
    return wrapper

def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        user_id = session.get('user_id', None)
        if not user_id:
            flash("Please login to continue!")
            return redirect(url_for('login'))
        user = User.query.get(user_id)
        if not user or user.role != 'admin':
            flash("You are not authorized to view this page!")
            return redirect(url_for('login'))
        return func(*args, **kwargs)
    return wrapper

@app.route('/register')
def register():
    return render_template('register.html')

@app.route('/customer_signup', methods=['GET', 'POST'])
def customer_signup():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        mobile = request.form['mobile']
        address = request.form['address']
        pincode = request.form['pincode']

        user = User(
            name=name,
            email=email,
            password=password,
            role='customer',
            mobile=mobile,
            address=address,
            pincode=pincode
        )

        try:
            db.session.add(user)
            db.session.commit()

            customer = Customer(id=user.id)
            db.session.add(customer)
            db.session.commit()

            flash("Customer account created successfully!", "success")
            return redirect(url_for('login')) 

        except Exception as e:
            db.session.rollback() 
            flash(f"An error occurred: {str(e)}", "danger")
            return redirect(url_for('customer_signup'))

    return render_template('customer_signup.html')

ALLOWED_EXTENSIONS = {'pdf'}
UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads')

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/professional_signup', methods=['GET', 'POST'])
def professional_signup():
    if request.method == 'POST':
        try:
            name = request.form['name']
            email = request.form['email']
            password = request.form['password']
            mobile = request.form['mobile']
            service_domain = request.form['service_domain']
            experience = request.form['experience']
            address = request.form['address']
            pincode = request.form['pincode']

            file = request.files.get('documents')
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                document_path = os.path.join(UPLOAD_FOLDER, filename)
                file.save(document_path)
                
                relative_document_path = f'{filename}'
            else:
                flash("Invalid file type or no file uploaded. Only PDF files are allowed.", "error")
                return redirect(request.url)

            user = User(
                name=name,
                email=email,
                password=password,
                role='professional',
                mobile=mobile,
                address=address,
                pincode=pincode,
            )
            db.session.add(user)
            db.session.flush()

            professional = Professional(
                id=user.id,
                service_domain=service_domain,
                experience=experience,
                documents=relative_document_path,
                status='pending'
            )
            db.session.add(professional)
            db.session.commit()

            flash("Professional account created successfully! Awaiting admin approval.", "success")
            return redirect(url_for('login'))

        except Exception as e:
            db.session.rollback()
            flash(f"An error occurred: {e}", "danger")
            return redirect(request.url)

    return render_template('professional_signup.html')

@app.route('/')
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')

    elif request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()

        if not user or user.password != password:
            flash("Invalid email or password!", "error")
            return redirect(url_for('login'))

        session['user_id'] = user.id 
        session['role'] = user.role
        session['name'] = user.name

        if user.role == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif user.role == 'customer':
            return redirect(url_for('customer_dashboard'))
        elif user.role == 'professional':
            return redirect(url_for('professional_dashboard'))
        else:
            flash("User role not recognized.", "error")
            return redirect(url_for('login'))
    
@app.route('/customer_dashboard')
def customer_dashboard():
    username = session.get('name')
    try:
        user_id = session.get('user_id')
        if not user_id:
            flash('Please log in to access the dashboard.', 'error')
            return redirect(url_for('login'))

        service_history = db.session.query(Service).filter(Service.customer_id == user_id).order_by(Service.id.desc()).all()
        return render_template('customer_dashboard.html', service_history=service_history, username = username)
    except Exception as e:
        flash(f'Error loading dashboard: {e}', 'error')
        return render_template('customer_dashboard.html', service_history=[])


@app.route('/customer_search', methods=['GET'])
def customer_search():
    service_type = request.args.get('service_type', '')
    status = request.args.get('status', '')
    user_id = session.get('user_id')

    customer = Customer.query.filter_by(id=user_id).first()

    if not customer:
        return render_template(
            'customer_search.html',
            services=[],
            selected_type=service_type,
            selected_status=status
        )

    query = Service.query

    if service_type:
        query = query.filter(Service.name == service_type)

    if status == 'current':
        query = query.filter(Service.customer_id == None)

    elif status == 'past':
        query = query.filter(Service.customer_id == customer.id)

    services = query.all()

    return render_template(
        'customer_search.html',
        services=services,
        selected_type=service_type,
        selected_status=status
    )

@app.route('/customer_summary')
def customer_summary():
    customer_id = session.get('user_id')
    
    if not customer_id:
        flash("You must be logged in to view your summary.", "danger")
        return redirect(url_for('login'))
    
    requested_count = Service.query.filter_by(customer_id=customer_id, status='requested').count()
    inprogress_count = Service.query.filter_by(customer_id=customer_id, status='inprogress').count()
    completed_count = Service.query.filter_by(customer_id=customer_id, status='completed').count()

    services_status_data = {
        'Requested': requested_count,
        'In-Progress': inprogress_count,
        'Completed': completed_count
    }
    

    fig, ax = plt.subplots()
    ax.bar(services_status_data.keys(), services_status_data.values())
    ax.set_xlabel('Service Status')
    ax.set_ylabel('Number of Services')
    ax.set_title('Services Status Overview')

    img = io.BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)
    services_status_plot = base64.b64encode(img.getvalue()).decode('utf-8')

    return render_template('customer_summary.html', 
                           requested_count=requested_count,
                           inprogress_count=inprogress_count,
                           completed_count=completed_count,
                           services_status_plot=services_status_plot)


@app.route('/professional_dashboard')
def professional_dashboard():
    if session.get('role') == 'professional':
        user_id = session.get('user_id')
        professional = Professional.query.filter_by(id=user_id).first()

        if not professional:
            flash('Professional not found.', 'error')
            return redirect(url_for('login'))

        domain = professional.service_domain
        if not domain:
            flash('No service domain assigned to this professional.', 'error')
            return redirect(url_for('login'))

        pending_services = db.session.query(Service, User).join(
            User, Service.customer_id == User.id
        ).filter(
            Service.professional_id == professional.id,
            Service.status == 'inprogress'
        ).all()

        today_services = db.session.query(Service, User).join(
            User, Service.customer_id == User.id
        ).filter(
            Service.name == domain,
            Service.status == 'requested'
        ).all()

        completed_services = db.session.query(Service, User).join(
            User, Service.customer_id == User.id
        ).filter(
            Service.professional_id == professional.id,
            Service.status == 'completed'
        ).all()

        return render_template(
            'professional_dashboard.html',
            professional=professional,
            pending_services=pending_services,
            today_services=today_services,
            completed_services=completed_services
        )

    flash('Access denied. Please log in.', 'error')
    return redirect(url_for('login'))



@app.route('/professional_search', methods=['GET', 'POST'])
def professional_search():
    user_id = session.get('user_id')

    service_requests = []

    if request.method == 'POST':
        search_by = request.form['search_by']
        search_input = request.form['search_input']
        query = Service.query.filter(Service.professional_id == user_id)

        if search_by == 'location' and search_input:
            service_requests = query.filter(Service.address.contains(search_input)).all()
        elif search_by == 'customer_name' and search_input:
            service_requests = query.join(Customer).filter(Customer.user.has(name=search_input)).all()
        elif search_by == 'date' and search_input:
            service_requests = query.filter(func.date(Service.date_created) == search_input).all()

    return render_template('professional_search.html', service_requests=service_requests)

@app.route('/professional_summary')
def professional_summary():
    user_id = session.get('user_id')

    if not user_id:
        return redirect(url_for('login'))
    user = User.query.filter_by(id=user_id).first()
    if user:
        professional = user.professional
    else:
        return redirect(url_for('login'))

    avg_rating = db.session.query(db.func.avg(Service.rating)).filter_by(professional_id=professional.id).scalar()
    service_counts = db.session.query(Service.status, db.func.count(Service.id)) \
                                .filter_by(professional_id=professional.id) \
                                .group_by(Service.status).all()

    ratings_plot = None
    if avg_rating is not None:
        fig, ax = plt.subplots()
        ax.bar(['Average Rating'], [avg_rating], color='skyblue')
        ax.set_title('Professional Average Rating')
        ax.set_ylabel('Average Rating')
        ax.set_ylim(0, 5)

        img = io.BytesIO()
        fig.savefig(img, format='png')
        img.seek(0)
        ratings_plot = base64.b64encode(img.getvalue()).decode('utf8')

    services_plot = None
    if service_counts:
        statuses = [service[0] for service in service_counts]
        counts = [service[1] for service in service_counts]

        fig, ax = plt.subplots()
        ax.pie(counts, labels=statuses, autopct='%1.1f%%', startangle=90, colors=['#ff9999','#66b3ff','#99ff99'])
        ax.set_title('Service Status (Jobs Completed vs. Jobs In Progress)')

        img = io.BytesIO()
        fig.savefig(img, format='png')
        img.seek(0)
        services_plot = base64.b64encode(img.getvalue()).decode('utf8')

    total_services_accepted = Service.query.filter_by(professional_id=professional.id).filter(Service.status.in_(['inprogress', 'completed'])).count()
    completed_services = Service.query.filter_by(professional_id=professional.id, status='completed').count()
    completion_rate = (completed_services / total_services_accepted) * 100 if total_services_accepted > 0 else 0

    return render_template('professional_summary.html', 
                           professional=professional,
                           ratings_plot=ratings_plot, 
                           services_plot=services_plot, 
                           avg_rating=avg_rating, 
                           total_services_accepted=total_services_accepted, 
                           completion_rate=completion_rate)


@app.route('/admin_dashboard', methods=['GET', 'POST'])
def admin_dashboard():
    professionals = Professional.query.filter_by(status='pending').all()

    service_requests = Service.query.filter_by(status='pending').all()

    service_requests_with_customers = []
    for request_data in service_requests:
        customer = Customer.query.get(request_data.customer_id)
        if customer and customer.user:
            service_requests_with_customers.append({
                'service_request': request_data,
                'customer_name': customer.user.name,
                'customer_email': customer.user.email,
                'customer_address': customer.user.address,
                'customer_mobile': customer.user.mobile
            })
        else:
            service_requests_with_customers.append({
                'service_request': request_data,
                'customer_name': "N/A",
                'customer_email': "N/A",
                'customer_address': "N/A",
                'customer_mobile': "N/A"
            })

    print(f"Pending professionals: {professionals}")
    print(f"Pending service requests: {service_requests_with_customers}")

    if request.method == 'POST':
        try:
            service_request_id = request.form.get('service_request_id')
            action = request.form.get('action')

            service_request = Service.query.get(service_request_id)
            if service_request:
                if action == 'accept':
                    service_request.status = 'requested'
                elif action == 'reject':
                    service_request.status = 'closed'

                db.session.commit()
                flash(f"Service request {action}ed successfully.", "success")
            else:
                flash("Service request not found.", "danger")
        except Exception as e:
            db.session.rollback()
            flash(f"An error occurred: {e}", "danger")

        return redirect(url_for('admin_dashboard'))

    return render_template(
        'admin_dashboard.html', 
        professionals=professionals, 
        service_requests_with_customers=service_requests_with_customers
    )

@app.route('/admin_search', methods=['GET', 'POST'])
def admin_search():
    services = None

    if request.method == 'POST':
        search_input = request.form.get('search_input')

        if search_input:
            services = Service.query.filter_by(name=search_input).all()

    return render_template('admin_search.html', services=services)

@app.route('/admin_service_view/<int:service_id>', methods=['GET', 'POST'])
def admin_service_view(service_id):
    service = Service.query.get_or_404(service_id)

    if request.method == 'POST':
        if service.status in ['requested', 'pending', 'inprogress']:
            service.status = 'closed'
            db.session.commit()
            flash('Service has been closed successfully.', 'success')
            return redirect(url_for('admin_service_view', service_id=service.id))

    return render_template('admin_service_view.html', service=service)

@app.route('/admin_summary')
def admin_summary():
    avg_rating = db.session.query(db.func.avg(Service.rating)).scalar()
    service_counts = db.session.query(Service.name, db.func.count(Service.id)).group_by(Service.name).all()
    ratings_plot = None
    if avg_rating:
        fig, ax = plt.subplots()
        ax.bar(['Average Rating'], [avg_rating], color='skyblue')
        ax.set_title('Overall Customer Ratings')
        ax.set_ylabel('Average Rating')
        ax.set_ylim(0, 5)

        img = io.BytesIO()
        fig.savefig(img, format='png')
        img.seek(0)
        ratings_plot = base64.b64encode(img.getvalue()).decode('utf8')

    services_plot = None
    if service_counts:
        service_names = [service[0] for service in service_counts]
        service_counts_values = [service[1] for service in service_counts]

        fig, ax = plt.subplots()
        sns.barplot(x=service_names, y=service_counts_values, ax=ax, palette='viridis')
        ax.set_title('Services Requested by Type')
        ax.set_xlabel('Service Type')
        ax.set_ylabel('Number of Requests')

        img = io.BytesIO()
        fig.savefig(img, format='png')
        img.seek(0)
        services_plot = base64.b64encode(img.getvalue()).decode('utf8')

    return render_template('admin_summary.html', 
                           ratings_plot=ratings_plot, 
                           services_plot=services_plot, 
                           avg_rating=avg_rating, 
                           service_counts=service_counts)

@app.route('/manage_services', methods=['GET', 'POST'])
def manage_services():
    services = Service.query.order_by(Service.id.desc()).all()
    
    if request.method == 'POST':
        # Here, we handle the "Close" button click
        service_id = request.form.get('service_id')
        service = Service.query.get(service_id)
        
        if service and service.status in ['In Progress', 'Requested']:
            service.status = 'Closed'
            db.session.commit()
            flash("Service has been closed successfully.", "success")
        
        return redirect(url_for('manage_services'))

    return render_template('manage_services.html', services=services)

@app.route('/manage_requests', methods=['GET', 'POST'])
def manage_requests():
    if request.method == 'POST':
        service_id = request.form.get('service_id')
        price = request.form.get('price')
        action = request.form.get('action')

        service = Service.query.get(service_id)
        if service and service.status == 'pending':
            service.price = float(price) if price else None
            if action == 'approve':
                service.status = 'requested'
            elif action == 'reject':
                service.status = 'closed'
            db.session.commit()

            flash(f"Service ID {service_id} has been {action} successfully!", "success")

    services = Service.query.filter_by(status='pending').all()

    return render_template('manage_requests.html', services=services)

@app.route('/manage_professionals', methods=['GET'])
def manage_professionals():
    pending_professionals = Professional.query.filter_by(status='pending').all()
    approved_professionals = Professional.query.filter_by(status='approved').all()

    return render_template('manage_professionals.html', 
                           pending_professionals=pending_professionals,
                           approved_professionals=approved_professionals)

@app.route('/delete_professional/<int:professional_id>', methods=['GET'])
def delete_professional(professional_id):
    professional = Professional.query.get(professional_id)
    if professional:
        professional.status = 'blocked'
        db.session.commit()
        flash("Professional has been blocked successfully.", "success")
    else:
        flash("Professional not found.", "danger")
    
    return redirect(url_for('manage_professionals'))

@app.route('/manage_customers', methods=['GET'])
def manage_customers():
    customers = Customer.query.all()
    return render_template('manage_customers.html', customers=customers)

@app.route('/delete_customer/<int:customer_id>', methods=['POST'])
def delete_customer(customer_id):
    try:
        customer = Customer.query.get(customer_id)
        if customer:
            db.session.delete(customer)
            db.session.commit()
            flash("Customer deleted successfully.", "success")
        else:
            flash("Customer not found.", "danger")
    except Exception as e:
        db.session.rollback()
        flash(f"An error occurred: {e}", "danger")

    return redirect(url_for('manage_customers'))

@app.route('/new_service', methods=['GET', 'POST'])
def new_service():
    if request.method == 'POST':
        admin_id = session.get('user_id')
        
        if not admin_id:
            return redirect(url_for('login'))
        
        service_name = request.form['service_name']
        description = request.form['description']
        base_price = request.form['base_price']
        address = request.form['address']
        
        new_service = Service(
            name=service_name,
            price=float(base_price),
            description=description,
            address=address,
            status='created',
            created_by=admin_id,
            date_created=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )

        db.session.add(new_service)
        db.session.commit()

        return redirect(url_for('admin_dashboard'))

    return render_template('new_service.html')

@app.route('/end_service/<int:service_id>', methods=['POST'])
def end_service(service_id):
    service = Service.query.get(service_id)
    if service and service.status in ['inprogress', 'requested']:
        service.status = 'closed'
        db.session.commit()
        flash("Service has been closed successfully.", "success")
    
    return redirect(url_for('manage_services'))

@app.route('/approve_professional/<int:professional_id>/<action>', methods=['GET'])
def approve_professional(professional_id, action):
    professional = Professional.query.get(professional_id)
    if professional:
        if action == 'accept':
            professional.status = 'approved'
        elif action == 'reject':
            professional.status = 'rejected'
        db.session.commit()
    return redirect(url_for('manage_professionals'))

@app.route('/get_services', methods=['GET'])
def get_services():
    category = request.args.get('category')
    if not category:
        flash("Invalid category", "danger")
        return redirect(url_for('customer_dashboard'))

    services = Service.query.filter_by(name=category, customer_id=None).all()
    service_history = Service.query.filter_by(customer_id=session.get('user_id')).all()
    return render_template(
        'customer_dashboard.html',
        services=services,
        category=category,
        service_history=service_history
    )

@app.route('/book_service', methods=['POST'])
def book_service():
    service_id = request.form.get('service_id')
    customer_id = session.get('user_id')

    if not service_id or not customer_id:
        flash("Invalid service or customer ID", "danger")
        return redirect(url_for('customer_dashboard'))

    service = Service.query.get(service_id)
    if not service:
        flash("Service not found", "danger")
        return redirect(url_for('customer_dashboard'))

    if service.customer_id:
        flash("Service already booked", "danger")
        return redirect(url_for('customer_dashboard'))

    service.customer_id = customer_id
    service.status = 'requested'
    db.session.commit()

    flash("Service booked successfully!", "success")
    return redirect(url_for('customer_dashboard'))

@app.route('/close_service/<int:service_id>', methods=['GET', 'POST'])
@login_required
def close_service(service_id):
    service = Service.query.get_or_404(service_id)

    if request.method == 'POST':
        service.rating = request.form['rating']
        service.remarks = request.form['remarks']
        service.status = 'completed'
        
        db.session.commit()

        flash('Service has been closed and reviewed successfully.', 'success')
        
        return redirect(url_for('customer_dashboard'))

    return render_template('close_service.html', service=service)
    
@app.route('/service_request', methods=['GET', 'POST'])
def service_request():
    user_id = session.get('user_id')
    if not user_id:
        flash("You need to log in to submit a service request.", "danger")
        return redirect(url_for('login'))

    user = User.query.get(user_id)
    if not user or user.role != 'customer':
        flash("Only customers can submit service requests.", "danger")
        return redirect(url_for('login'))

    if request.method == 'GET':
        return render_template('service_request.html')

    elif request.method == 'POST':
        service_name = request.form.get('service_type')
        description = request.form.get('description')
        address = request.form.get('address')
        contact_number = request.form.get('contact_number')
        new_service = Service(
            name=service_name,
            description=description,
            address=address,
            customer_id=user.customer.id,
            created_by=user_id,
            status='pending',
            date_created=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )

        try:
            db.session.add(new_service)
            db.session.commit()
            flash("Service request submitted successfully!", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"An error occurred: {str(e)}", "danger")

        return redirect(url_for('customer_dashboard'))
    
@app.route('/view_service/<int:service_id>', methods=['GET'])
def view_service(service_id):
    service = db.session.query(Service).join(Customer).join(User).filter(Service.id == service_id).first_or_404()
    
    return render_template('view_service.html', service=service)

@app.route('/accept_service/<int:service_id>', methods=['POST'])
def accept_service(service_id):
    service = Service.query.get_or_404(service_id)
    professional = session.get('user_id')
    if service and professional:
        if service.status != 'inprogress':
            service.professional_id = professional
            service.status = 'inprogress'
            try:
                db.session.commit()
                flash("Service accepted successfully.", "success")
            except Exception as e:
                db.session.rollback()
                flash(f"An error occurred while accepting the service: {e}", "danger")
        else:
            flash("This service is already in progress.", "warning")

        return redirect(url_for('professional_dashboard'))
    else:
        flash("Professional not found or service not available.", "danger")
        return redirect(url_for('view_service', service_id=service.id)) 
    
@app.route('/service_history/<int:service_id>')
@login_required
def service_history(service_id):
    service = Service.query.get_or_404(service_id)
    return render_template('service_history.html', service=service)

@app.route('/service_details/<int:service_id>', methods=['GET', 'POST'])
@login_required
def service_details(service_id):
    service = Service.query.get_or_404(service_id)
    user_id = session.get('user_id')
    if service.customer_id != user_id:
        return redirect(url_for('service_history'))

    close_service = service.status in ['inprogress', 'requested', 'pending']

    if request.method == 'POST' and close_service:
        service.status = 'closed'
        db.session.commit()
        return redirect(url_for('service_history'))

    return render_template('service_details.html', service=service, close_service=close_service)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('role', None)
    return redirect(url_for('login'))