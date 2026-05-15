from app import app, db
from sqlalchemy import text

with app.app_context():
    try:
        db.session.execute(text("ALTER TABLE user ADD COLUMN is_admin BOOLEAN DEFAULT 0;"))
        db.session.commit()
        print("Successfully added is_admin column.")
    except Exception as e:
        print("Column might already exist or error occurred:", e)
        
    # Make existing users admin if their name is admin
    try:
        db.session.execute(text("UPDATE user SET is_admin = 1 WHERE username = 'admin';"))
        db.session.commit()
        print("Set admin user to is_admin=1")
    except Exception as e:
        print("Error updating admin user:", e)
