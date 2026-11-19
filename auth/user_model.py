"""
auth/user_model.py — Flask-Login compatible User class.
"""

from flask_login import UserMixin


class User(UserMixin):
    def __init__(self, user_dict):
        self.id = user_dict['id']
        self.username = user_dict['username']
        self.email = user_dict['email']
        self.role = user_dict['role']
        self.full_name = user_dict.get('full_name', '')
        self.area = user_dict.get('area', '')

    def is_admin(self):
        return self.role == 'admin'

    def get_id(self):
        return str(self.id)
