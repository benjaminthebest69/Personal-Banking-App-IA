# models.py
import os
import sqlite3
from datetime import datetime, timedelta
import logging
DATABASE = 'database.db'

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(levelname)s:%(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

DATABASE = os.path.join(os.path.dirname(__file__), 'database.db') #ensure database in right diredctory hopefully

def get_connection():
    """
    Establishes a connection to the SQLite database.
    Enables foreign key constraints.
    """
    conn = sqlite3.connect(DATABASE)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    """
    Initializes the database with required tables.
    If tables already exist, this function ensures they have the necessary schema.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Create Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)
    
    # Create Categories table with user_id
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE
        )
    """)
    
    # Create Expenses table with user_id
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            category TEXT NOT NULL,
            amount REAL NOT NULL,
            user_id INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE
        )
    """)
    
    # Create RecurringPayments table with user_id
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS RecurringPayments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            amount REAL NOT NULL,
            due_date TEXT NOT NULL,
            frequency TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE
        )
    """)
    
    # Create Budget table with user_id
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Budget (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            month TEXT NOT NULL,
            amount REAL NOT NULL,
            user_id INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE
        )
    """)
    
    conn.commit()
    conn.close()

class User:
    """Handles user-related database operations."""

    @staticmethod
    def add_user(username, password):
        """
        Adds a new user to the database.
        
        Args:
            username (str): The desired username.
            password (str): The desired password.
        
        Raises:
            ValueError: If the username already exists.
        """
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO Users (username, password)
                VALUES (?, ?)
            """, (username, password))
            conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            raise ValueError("Username already exists.")
        finally:
            conn.close()

    @staticmethod
    def authenticate(username, password):
        """
        Authenticates a user and returns the user_id if successful.
        
        Args:
            username (str): The username.
            password (str): The password.
        
        Returns:
            int or None: The user's ID if authentication is successful; otherwise, None.
        """
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id FROM Users
            WHERE username = ? AND password = ?
        """, (username, password))
        result = cursor.fetchone()
        conn.close()
        if result:
            return result[0]
        return None

class Category:
    """Handles category-related database operations."""

    @staticmethod
    def add(name):
        if not name or not isinstance(name, str):
            raise ValueError("Category name must be a non-empty string.")
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO Categories (name)
                VALUES (?)
            """, (name,))
            conn.commit()
            conn.close()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            raise ValueError("Category already exists.")
        finally:
            conn.close()

    @staticmethod
    def get_all(user_id):
        """
        Retrieves all categories for a specific user.
        
        Args:
            user_id (int): The ID of the user.
        
        Returns:
            list: A list of category names.
        """
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name FROM Categories
            WHERE user_id = ?
            ORDER BY name ASC
        """, (user_id,))
        categories = [row[0] for row in cursor.fetchall()]
        conn.close()
        return categories

    @staticmethod
    def delete(name, user_id):
        """
        Deletes a category for a specific user.
        
        Args:
            name (str): The name of the category to delete.
            user_id (int): The ID of the user.
        """
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM Categories
            WHERE name = ? AND user_id = ?
        """, (name, user_id))
        conn.commit()
        conn.close()

class Expense:
    """Handles expense-related database operations."""

    @staticmethod
    def add(date, category, amount, user_id):
        """
        Adds a new expense to the database.
        
        Args:
            date (str): The date of the expense in 'YYYY-MM-DD' format.
            category (str): The category of the expense.
            amount (float): The amount of the expense.
            user_id (int): The ID of the user.
        """
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO Expenses (date, category, amount, user_id)
            VALUES (?, ?, ?, ?)
        """, (date, category, amount, user_id))
        conn.commit()
        conn.close()

    @staticmethod
    def get_all(user_id):
        """
        Retrieves all expenses for a specific user.
        
        Args:
            user_id (int): The ID of the user.
        
        Returns:
            list: A list of tuples containing expense details.
        """
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, date, category, amount FROM Expenses
            WHERE user_id = ?
            ORDER BY date DESC
        """, (user_id,))
        expenses = cursor.fetchall()
        conn.close()
        return expenses

    @staticmethod
    def get_spending_since(start_date, user_id):
        """
        Calculates total spending since a specific date for a user.
        
        Args:
            start_date (str): The start date in 'YYYY-MM-DD' format.
            user_id (int): The ID of the user.
        
        Returns:
            float: Total spending since the start date.
        """
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT SUM(amount) FROM Expenses
            WHERE date >= ? AND user_id = ?
        """, (start_date, user_id))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result[0] else 0.0

    @staticmethod
    def update(expense_id, new_date, new_category, new_amount, user_id):
        """
        Updates an existing expense.
        
        Args:
            expense_id (int): The ID of the expense to update.
            new_date (str): The new date in 'YYYY-MM-DD' format.
            new_category (str): The new category.
            new_amount (float): The new amount.
            user_id (int): The ID of the user.
        
        Raises:
            ValueError: If the expense does not belong to the user.
        """
        conn = get_connection()
        cursor = conn.cursor()
        # Verify ownership
        cursor.execute("""
            SELECT id FROM Expenses
            WHERE id = ? AND user_id = ?
        """, (expense_id, user_id))
        if not cursor.fetchone():
            conn.close()
            raise ValueError("Expense not found or does not belong to the user.")
        
        cursor.execute("""
            UPDATE Expenses
            SET date = ?, category = ?, amount = ?
            WHERE id = ? AND user_id = ?
        """, (new_date, new_category, new_amount, expense_id, user_id))
        conn.commit()
        conn.close()

    @staticmethod
    def delete(expense_id, user_id):
        """
        Deletes an expense from the database.
        
        Args:
            expense_id (int): The ID of the expense to delete.
            user_id (int): The ID of the user.
        
        Raises:
            ValueError: If the expense does not belong to the user.
        """
        conn = get_connection()
        cursor = conn.cursor()
        # Verify ownership
        cursor.execute("""
            SELECT id FROM Expenses
            WHERE id = ? AND user_id = ?
        """, (expense_id, user_id))
        if not cursor.fetchone():
            conn.close()
            raise ValueError("Expense not found or does not belong to the user.")
        
        cursor.execute("""
            DELETE FROM Expenses
            WHERE id = ? AND user_id = ?
        """, (expense_id, user_id))
        conn.commit()
        conn.close()

    @staticmethod
    def get_daily_spending(user_id):
        """
        Retrieves daily spending data for charting.
        
        Args:
            user_id (int): The ID of the user.
        
        Returns:
            list: A list of tuples containing date and total amount spent on that date.
        """
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT date, SUM(amount) FROM Expenses
            WHERE user_id = ?
            GROUP BY date
            ORDER BY date
        """, (user_id,))
        data = cursor.fetchall()
        conn.close()
        return data

class RecurringPayment:
    """Handles recurring payment-related database operations."""

    @staticmethod
    def add(name, amount, due_date, frequency, user_id):
        """
        Adds a new recurring payment to the database.
        
        Args:
            name (str): The name of the payment.
            amount (float): The amount of the payment.
            due_date (str): The due date in 'YYYY-MM-DD' format.
            frequency (str): The frequency ('Weekly', 'Monthly', 'Yearly').
            user_id (int): The ID of the user.
        """
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO RecurringPayments (name, amount, due_date, frequency, user_id)
            VALUES (?, ?, ?, ?, ?)
        """, (name, amount, due_date, frequency, user_id))
        conn.commit()
        conn.close()

    @staticmethod
    def get_all(user_id):
        """
        Retrieves all recurring payments for a specific user.
        
        Args:
            user_id (int): The ID of the user.
        
        Returns:
            list: A list of tuples containing recurring payment details.
        """
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, amount, due_date, frequency FROM RecurringPayments
            WHERE user_id = ?
            ORDER BY due_date ASC
        """, (user_id,))
        payments = cursor.fetchall()
        conn.close()
        return payments

    @staticmethod
    def delete(payment_id, user_id):
        """
        Deletes a recurring payment from the database.
        
        Args:
            payment_id (int): The ID of the recurring payment to delete.
            user_id (int): The ID of the user.
        
        Raises:
            ValueError: If the payment does not belong to the user.
        """
        conn = get_connection()
        cursor = conn.cursor()
        # Verify ownership
        cursor.execute("""
            SELECT id FROM RecurringPayments
            WHERE id = ? AND user_id = ?
        """, (payment_id, user_id))
        if not cursor.fetchone():
            conn.close()
            raise ValueError("Recurring payment not found or does not belong to the user.")
        
        cursor.execute("""
            DELETE FROM RecurringPayments
            WHERE id = ? AND user_id = ?
        """, (payment_id, user_id))
        conn.commit()
        conn.close()

    @staticmethod
    def mark_as_paid(payment_id, payment_date, user_id):
        """
        Marks a recurring payment as paid and updates its due date based on frequency.
        
        Args:
            payment_id (int): The ID of the recurring payment.
            payment_date (str): The date when the payment was made in 'YYYY-MM-DD' format.
            user_id (int): The ID of the user.
        
        Raises:
            ValueError: If the payment does not belong to the user.
        """
        conn = get_connection()
        cursor = conn.cursor()
        
        # Verify ownership and get frequency
        cursor.execute("""
            SELECT frequency FROM RecurringPayments
            WHERE id = ? AND user_id = ?
        """, (payment_id, user_id))
        result = cursor.fetchone()
        if not result:
            conn.close()
            raise ValueError("Recurring payment not found or does not belong to the user.")
        
        frequency = result[0]
        next_due_date = calculate_next_due_date(datetime.strptime(payment_date, '%Y-%m-%d').date(), frequency)
        next_due_date_str = next_due_date.strftime('%Y-%m-%d')
        
        # Update due_date
        cursor.execute("""
            UPDATE RecurringPayments
            SET due_date = ?
            WHERE id = ? AND user_id = ?
        """, (next_due_date_str, payment_id, user_id))
        conn.commit()
        conn.close()

def calculate_next_due_date(current_due_date, frequency):
    """
    Calculates the next due date based on the frequency.
    
    Args:
        current_due_date (datetime.date): The current due date.
        frequency (str): The frequency ('Weekly', 'Monthly', 'Yearly').
    
    Returns:
        datetime.date: The next due date.
    """
    if frequency == "Weekly":
        return current_due_date + timedelta(weeks=1)
    elif frequency == "Monthly":
        month = current_due_date.month
        year = current_due_date.year + (month // 12)
        month = (month % 12) + 1
        day = min(current_due_date.day, 28)  # To handle months with fewer days
        return datetime(year, month, day).date()
    elif frequency == "Yearly":
        return datetime(current_due_date.year + 1, current_due_date.month, current_due_date.day).date()
    else:
        # Default to next month if frequency is unrecognized
        month = current_due_date.month
        year = current_due_date.year + (month // 12)
        month = (month % 12) + 1
        day = min(current_due_date.day, 28)
        return datetime(year, month, day).date()

class Budget:
    """Handles budget-related database operations."""

    @staticmethod
    def set_monthly_budget(month, amount, user_id):
        """
        Sets or updates the monthly budget for a specific user.
        
        Args:
            month (str): The month in 'YYYY-MM' format.
            amount (float): The budget amount.
            user_id (int): The ID of the user.
        """
        conn = get_connection()
        cursor = conn.cursor()
        
        # Check if budget for the month already exists
        cursor.execute("""
            SELECT id FROM Budget
            WHERE month = ? AND user_id = ?
        """, (month, user_id))
        result = cursor.fetchone()
        
        if result:
            # Update existing budget
            cursor.execute("""
                UPDATE Budget
                SET amount = ?
                WHERE month = ? AND user_id = ?
            """, (amount, month, user_id))
        else:
            # Insert new budget
            cursor.execute("""
                INSERT INTO Budget (month, amount, user_id)
                VALUES (?, ?, ?)
            """, (month, amount, user_id))
        
        conn.commit()
        conn.close()

    @staticmethod
    def get_monthly_budget(month, user_id):
        """
        Retrieves the monthly budget for a specific user.
        
        Args:
            month (str): The month in 'YYYY-MM' format.
            user_id (int): The ID of the user.
        
        Returns:
            float or None: The budget amount if set; otherwise, None.
        """
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT amount FROM Budget
            WHERE month = ? AND user_id = ?
        """, (month, user_id))
        result = cursor.fetchone()
        conn.close()
        if result:
            return result[0]
        return None

def migrate_add_user_id():
    """
    Adds user_id column to existing tables if not present.
    This is useful if you had existing tables without user_id and need to add it now.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Check and add user_id to Expenses table
    cursor.execute("PRAGMA table_info(Expenses)")
    columns = [info[1] for info in cursor.fetchall()]
    if 'user_id' not in columns:
        cursor.execute("""
            ALTER TABLE Expenses
            ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1
        """)
        # Update the existing records with a default user_id or assign appropriately
        # Here, we're setting a default user_id of 1; adjust as needed
        cursor.execute("""
            UPDATE Expenses
            SET user_id = 1
        """)
        # Ensure user_id 1 exists in Users table
        cursor.execute("""
            INSERT OR IGNORE INTO Users (id, username, password)
            VALUES (1, 'default_user', 'password123')
        """)
        logger.info("Added user_id column to Expenses table.")
    
    # Similarly, add user_id to Categories, RecurringPayments, Budget tables
    cursor.execute("PRAGMA table_info(Categories)")
    columns = [info[1] for info in cursor.fetchall()]
    if 'user_id' not in columns:
        cursor.execute("""
            ALTER TABLE Categories
            ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1
        """)
        cursor.execute("""
            UPDATE Categories
            SET user_id = 1
        """)
        cursor.execute("""
            INSERT OR IGNORE INTO Users (id, username, password)
            VALUES (1, 'default_user', 'password123')
        """)
        logger.info("Added user_id column to Categories table.")
    
    cursor.execute("PRAGMA table_info(RecurringPayments)")
    columns = [info[1] for info in cursor.fetchall()]
    if 'user_id' not in columns:
        cursor.execute("""
            ALTER TABLE RecurringPayments
            ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1
        """)
        cursor.execute("""
            UPDATE RecurringPayments
            SET user_id = 1
        """)
        cursor.execute("""
            INSERT OR IGNORE INTO Users (id, username, password)
            VALUES (1, 'default_user', 'password123')
        """)
        logger.info("Added user_id column to RecurringPayments table.")
    
    cursor.execute("PRAGMA table_info(Budget)")
    columns = [info[1] for info in cursor.fetchall()]
    if 'user_id' not in columns:
        cursor.execute("""
            ALTER TABLE Budget
            ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1
        """)
        cursor.execute("""
            UPDATE Budget
            SET user_id = 1
        """)
        cursor.execute("""
            INSERT OR IGNORE INTO Users (id, username, password)
            VALUES (1, 'default_user', 'password123')
        """)
        logger.info("Added user_id column to Budget table.")
    
    conn.commit()
    conn.close()

# Initialize the database when models.py is run directly
if __name__ == "__main__":
    init_db()
    migrate_add_user_id
    print("Database initialized successfully.")
