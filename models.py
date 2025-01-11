from flask_sqlalchemy import SQLAlchemy
from main import app

db = SQLAlchemy(app)

class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(80), nullable=False)
    address = db.Column(db.String(200), nullable=True)
    pincode = db.Column(db.String(6), nullable=True)
    mobile = db.Column(db.String(15), nullable=True)

    customer = db.relationship('Customer', backref='user', uselist=False)
    professional = db.relationship('Professional', backref='user', uselist=False)

    def __repr__(self):
        return f"<User {self.name}>"

    def check_password(self, password):
        return self.password == password


class Customer(db.Model):
    __tablename__ = 'customer'
    id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)

    def __repr__(self):
        return f"<Customer {self.user.name}>"


class Professional(db.Model):
    __tablename__ = 'professional'
    id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    service_domain = db.Column(db.String(120), nullable=False)
    experience = db.Column(db.Integer, nullable=False)
    documents = db.Column(db.String(120), nullable=True)

    status = db.Column(db.String(20), default='pending')

    def __repr__(self):
        return f"<Professional {self.user.name}>"


class Service(db.Model):
    __tablename__ = 'service'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=True)
    description = db.Column(db.String(500), nullable=False)
    address = db.Column(db.String(255))
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) 
    creator = db.relationship('User', backref='created_services')
    status = db.Column(db.String(50), default='accepted')
    date_created = db.Column(db.String(50), nullable=False)
    professional_id = db.Column(db.Integer, db.ForeignKey('professional.id'), nullable=True) 
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=True)
    remarks = db.Column(db.Text, nullable=True)
    rating = db.Column(db.Integer, nullable=True)
    
    professional = db.relationship('Professional', backref='assigned_services', lazy=True)
    customer = db.relationship('Customer', backref='booked_services', lazy=True)
    
    def __repr__(self):
        return f"<Service {self.name}>"



with app.app_context():
    db.create_all()
    first_admin = User.query.filter_by(role='admin').first()
    if not first_admin:
        admin = User(
            name="admin",
            email="admin@example.com",
            password="admin",  
            role="admin",
            address="",      
            pincode="",       
            mobile=""     
        )
        db.session.add(admin)
        db.session.commit()
