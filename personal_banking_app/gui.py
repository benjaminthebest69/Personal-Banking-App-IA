# gui.py

import logging
import tkinter as tk
from tkinter import messagebox, simpledialog
from tkinter import ttk
from datetime import datetime, timedelta
from tkcalendar import DateEntry as TkDateEntry
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import csv
from models import User, Expense, Category, RecurringPayment, Budget, calculate_next_due_date, init_db 

# Configure logging with multiple levels and console output
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Capture all levels of logs

# File handler for logging (errors only)
file_handler = logging.FileHandler('app.log')
file_handler.setLevel(logging.ERROR)
file_formatter = logging.Formatter('%(asctime)s %(levelname)s:%(message)s')
file_handler.setFormatter(file_formatter)

# Console handler for logging (info and above)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('%(levelname)s: %(message)s')
console_handler.setFormatter(console_formatter)

# Add handlers to the logger if not already added
if not logger.handlers:
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)


class CustomDateEntry(TkDateEntry):
    """Custom DateEntry that ignores the 'style' parameter."""
    def __init__(self, master=None, **kwargs):
        kwargs.pop('style', None)  # Remove 'style' if present
        super().__init__(master, **kwargs)


class PersonalBankingApp(tk.Tk):
    """Main application class for the Personal Banking App."""

    def __init__(self):
        super().__init__()
        self.title("Personal Banking App")
        self.configure(bg="#FFFFFF")
        self.geometry("1200x800")  # Increased default size for better responsiveness
        self.minsize(1000, 700)

        #intialise Satabase
        init_db()

        # Current logged-in user ID
        self.current_user_id = None
        self.current_user = None  # Optional: Store username if needed

        # Configure styles
        style = ttk.Style(self)
        style.configure('TLabel', font=('Helvetica Neue', 12))
        style.configure('TButton', font=('Helvetica Neue', 12), padding=6)
        style.configure('Header.TLabel', font=('Helvetica Neue', 24, 'bold'))
        style.configure('SubHeader.TLabel', font=('Helvetica Neue', 16, 'bold'))
        style.configure('TEntry', font=('Helvetica Neue', 12))
        style.configure('TCombobox', font=('Helvetica Neue', 12))
        style.configure('Accent.TButton', foreground='white', background='#007acc')
        style.map('Accent.TButton',
                  foreground=[('pressed', 'white'), ('active', 'white')],
                  background=[('pressed', '!disabled', '#005f99'), ('active', '#005f99')])
        style.configure('Danger.TButton', foreground='white', background='#d9534f')
        style.map('Danger.TButton',
                  foreground=[('pressed', 'white'), ('active', 'white')],
                  background=[('pressed', '!disabled', '#c9302c'), ('active', '#c9302c')])
        style.configure('Success.TButton', foreground='white', background='#5cb85c')
        style.map('Success.TButton',
                  foreground=[('pressed', 'white'), ('active', 'white')],
                  background=[('pressed', '!disabled', '#449d44'), ('active', '#449d44')])
        style.configure('Warning.TButton', foreground='white', background='#f0ad4e')
        style.map('Warning.TButton',
                  foreground=[('pressed', 'white'), ('active', 'white')],
                  background=[('pressed', '!disabled', '#ec971f'), ('active', '#ec971f')])

        self.frames = {}
        self.create_frames()
        self.show_frame(LoginPage)  # Start with LoginPage

        # Start checking alerts
        self.check_alerts()

    def create_frames(self):
        """Create and store frames for navigation."""
        container = ttk.Frame(self)
        container.pack(side="top", fill="both", expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(1, weight=1)

        self.navbar = NavigationBar(container, self)
        self.navbar.grid(row=0, column=0, sticky="ns")
        self.navbar.configure(width=250)  # Increased navbar width for better accessibility

        content_frame = ttk.Frame(container)
        content_frame.grid(row=0, column=1, sticky="nsew")
        content_frame.grid_rowconfigure(0, weight=1)
        content_frame.grid_columnconfigure(0, weight=1)

        for F in (
            LoginPage, RegisterPage, HomePage, AddExpensePage, ViewExpensesPage, CategoryPage,
            RecurringPaymentsPage, SpendingSummaryPage, SetBudgetPage
        ):
            frame = F(content_frame, self)
            self.frames[F] = frame
            frame.grid(row=0, column=0, sticky="nsew")

    def show_frame(self, frame_class):
        """Display the specified frame."""
        frame = self.frames[frame_class]
        frame.refresh()
        frame.tkraise()
        self.navbar.highlight_button(frame_class)

    def check_alerts(self):
        """Continuously checks for upcoming recurring payments and budget alerts."""
        def alert():
            if self.current_user_id:
                self.check_recurring_payments()
                self.check_budget()
            # Schedule the next check in 24 hours (86400000 milliseconds)
            self.after(86400000, alert)

        # Start the alert function
        alert()

    def check_recurring_payments(self):
        """Check for upcoming recurring payments."""
        try:
            payments = RecurringPayment.get_all(self.current_user_id)
            today = datetime.now().date()
            for payment in payments:
                payment_id, name, amount, due_date_str, frequency = payment
                due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
                days_until_due = (due_date - today).days

                if days_until_due == 1:
                    messagebox.showwarning(
                        "Payment Due Tomorrow",
                        f"The payment '{name}' of ${amount:.2f} is due tomorrow."
                    )
                    logger.info("Payment '%s' due tomorrow.", name)
                elif days_until_due == 0:
                    messagebox.showwarning(
                        "Payment Due Today",
                        f"The payment '{name}' of ${amount:.2f} is due today."
                    )
                    logger.info("Payment '%s' due today.", name)
                elif days_until_due < 0:
                    # Update due date based on frequency
                    new_due_date = calculate_next_due_date(due_date, frequency)
                    RecurringPayment.update_due_date(payment_id, new_due_date.strftime('%Y-%m-%d'))
                    logger.info("Updated due date for payment '%s' to %s.", name, new_due_date.strftime('%Y-%m-%d'))
        except Exception as e:
            logger.exception("Error in check_recurring_payments: %s", e)
            messagebox.showerror("Error", f"An error occurred while checking recurring payments:\n{e}")

    def check_budget(self):
        """Check if the user is exceeding their monthly budget."""
        try:
            today = datetime.now().date()
            current_month = today.strftime('%Y-%m')
            budget_amount = Budget.get_monthly_budget(current_month, self.current_user_id)
            if budget_amount is not None:
                start_of_month = today.replace(day=1).strftime('%Y-%m-%d')
                spending = Expense.get_spending_since(start_of_month, self.current_user_id)
                if spending > budget_amount:
                    messagebox.showwarning(
                        "Budget Exceeded",
                        f"You have exceeded your budget for this month!\n"
                        f"Budget: ${budget_amount:.2f}\n"
                        f"Spending: ${spending:.2f}"
                    )
                    logger.warning("Budget exceeded for %s: Budget=%.2f, Spending=%.2f", current_month, budget_amount, spending)
        except Exception as e:
            logger.exception("Error in check_budget: %s", e)
            messagebox.showerror("Error", f"An error occurred while checking budget:\n{e}")


class NavigationBar(ttk.Frame):
    """Navigation bar for the application."""

    def __init__(self, parent, controller):
        """
        Initialize the NavigationBar.

        Args:
            parent (ttk.Frame): The parent frame.
            controller (PersonalBankingApp): The main application controller.
        """
        super().__init__(parent)
        self.controller = controller

        self.configure(padding=(10, 20))
        self.buttons = {}

        # Buttons for navigation
        nav_items = [
            ("Home", HomePage),
            ("Add Expense", AddExpensePage),
            ("View Expenses", ViewExpensesPage),
            ("Categories", CategoryPage),
            ("Recurring Payments", RecurringPaymentsPage),
            ("Spending Summary", SpendingSummaryPage),
            ("Set Budget", SetBudgetPage),
            ("Logout", None),  # Logout handled separately
        ]

        for text, frame in nav_items:
            if text == "Logout":
                button = ttk.Button(
                    self,
                    text=text,
                    command=self.logout,
                    style='Danger.TButton',
                    padding=10
                )
            else:
                button = ttk.Button(
                    self,
                    text=text,
                    command=lambda f=frame: controller.show_frame(f),
                    style='TButton',
                    padding=10
                )
            button.pack(fill='x', pady=5)
            self.buttons[frame] = button

    def highlight_button(self, frame_class):
        """
        Highlight the active navigation button.

        Args:
            frame_class (class): The frame class to highlight.
        """
        for frame, button in self.buttons.items():
            if frame == frame_class:
                button.configure(style='Accent.TButton')
            else:
                if isinstance(button, ttk.Button) and button['text'] == "Logout":
                    button.configure(style='Danger.TButton')
                else:
                    button.configure(style='TButton')

    def logout(self):
        """Handle user logout."""
        confirm = messagebox.askyesno("Logout", "Are you sure you want to logout?")
        if confirm:
            self.controller.current_user_id = None
            self.controller.current_user = None
            self.controller.show_frame(LoginPage)
            logger.info("User logged out.")


class LoginPage(ttk.Frame):
    """Login page for the application."""

    def __init__(self, parent, controller):
        """
        Initialize the LoginPage.

        Args:
            parent (ttk.Frame): The parent frame.
            controller (PersonalBankingApp): The main application controller.
        """
        super().__init__(parent)
        self.controller = controller

        ttk.Label(
            self, text="Login", style='Header.TLabel'
        ).pack(pady=40)

        form_frame = ttk.Frame(self)
        form_frame.pack(pady=10)

        # Username
        ttk.Label(form_frame, text="Username:").grid(
            row=0, column=0, padx=5, pady=5, sticky='e'
        )
        self.username_entry = ttk.Entry(form_frame)
        self.username_entry.grid(row=0, column=1, padx=5, pady=5)

        # Password
        ttk.Label(form_frame, text="Password:").grid(
            row=1, column=0, padx=5, pady=5, sticky='e'
        )
        self.password_entry = ttk.Entry(form_frame, show="*")
        self.password_entry.grid(row=1, column=1, padx=5, pady=5)

        # Buttons
        button_frame = ttk.Frame(self)
        button_frame.pack(pady=20)

        ttk.Button(
            button_frame, text="Login", command=self.login, style='Accent.TButton'
        ).grid(row=0, column=0, padx=10)
        ttk.Button(
            button_frame, text="Register", command=lambda: controller.show_frame(RegisterPage), style='TButton'
        ).grid(row=0, column=1, padx=10)

    def login(self):
        """Handles user login."""
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()

        if not username or not password:
            messagebox.showerror("Input Error", "Please enter both username and password.")
            return

        try:
            user_id = User.authenticate(username, password)
            if user_id:
                self.controller.current_user_id = user_id
                self.controller.current_user = username
                messagebox.showinfo("Success", f"Welcome, {username}!")
                self.controller.show_frame(HomePage)
                self.clear_entries()
            else:
                messagebox.showerror("Authentication Failed", "Invalid username or password.")
        except Exception as e:
            logger.exception("Error during login: %s", e)
            messagebox.showerror("Error", f"An error occurred during login:\n{e}")

    def clear_entries(self):
        """Clear the input fields."""
        self.username_entry.delete(0, tk.END)
        self.password_entry.delete(0, tk.END)

    def refresh(self):
        """Refresh the login page."""
        self.clear_entries()

class RegisterPage(ttk.Frame):
    """Registration page for new users."""

    def __init__(self, parent, controller):
        """
        Initialize the RegisterPage.

        Args:
            parent (ttk.Frame): The parent frame.
            controller (PersonalBankingApp): The main application controller.
        """
        super().__init__(parent)
        self.controller = controller

        ttk.Label(
            self, text="Register", style='Header.TLabel'
        ).pack(pady=40)

        form_frame = ttk.Frame(self)
        form_frame.pack(pady=10)

        # Username
        ttk.Label(form_frame, text="Username:").grid(
            row=0, column=0, padx=5, pady=5, sticky='e'
        )
        self.username_entry = ttk.Entry(form_frame)
        self.username_entry.grid(row=0, column=1, padx=5, pady=5)

        # Password
        ttk.Label(form_frame, text="Password:").grid(
            row=1, column=0, padx=5, pady=5, sticky='e'
        )
        self.password_entry = ttk.Entry(form_frame, show="*")
        self.password_entry.grid(row=1, column=1, padx=5, pady=5)

        # Confirm Password
        ttk.Label(form_frame, text="Confirm Password:").grid(
            row=2, column=0, padx=5, pady=5, sticky='e'
        )
        self.confirm_password_entry = ttk.Entry(form_frame, show="*")
        self.confirm_password_entry.grid(row=2, column=1, padx=5, pady=5)

        # Buttons
        button_frame = ttk.Frame(self)
        button_frame.pack(pady=20)

        ttk.Button(
            button_frame, text="Register", command=self.register, style='Accent.TButton'
        ).grid(row=0, column=0, padx=10)
        ttk.Button(
            button_frame, text="Back to Login", command=lambda: controller.show_frame(LoginPage), style='TButton'
        ).grid(row=0, column=1, padx=10)

    def register(self):
        """Handles user registration."""
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()
        confirm_password = self.confirm_password_entry.get().strip()

        if not username or not password or not confirm_password:
            messagebox.showerror("Input Error", "All fields are required.")
            return

        if password != confirm_password:
            messagebox.showerror("Input Error", "Passwords do not match.")
            return

        try:
            User.add_user(username, password)
            messagebox.showinfo("Success", "Registration successful! You can now log in.")
            self.controller.show_frame(LoginPage)
            self.clear_entries()
        except ValueError as ve:
            messagebox.showerror("Registration Failed", str(ve))
        except Exception as e:
            logger.exception("Error during registration: %s", e)
            messagebox.showerror("Error", f"An error occurred during registration:\n{e}")

    def clear_entries(self):
        """Clear the input fields."""
        self.username_entry.delete(0, tk.END)
        self.password_entry.delete(0, tk.END)
        self.confirm_password_entry.delete(0, tk.END)

    def refresh(self):
        """Refresh the registration page."""
        self.clear_entries()
class HomePage(ttk.Frame):
        """Home page displaying a rundown of today’s expenses, to-do list, and monthly payments."""
    
        def __init__(self, parent, controller):
            """
            Initialize the HomePage.
    
            Args:
                parent (ttk.Frame): The parent frame.
                controller (PersonalBankingApp): The main application controller.
            """
            super().__init__(parent)
            self.controller = controller
    
            # Set the header
            ttk.Label(
                self, text="Dashboard", style='Header.TLabel'
            ).pack(pady=20)
    
            # Frame for today's expenses
            self.todays_expenses_frame = self.create_todays_expenses_section()
            self.todays_expenses_frame.pack(pady=10, padx=20, fill='both', expand=True)
    
            # Frame for to-do list
            self.todo_list_frame = self.create_todo_list_section()
            self.todo_list_frame.pack(pady=10, padx=20, fill='both', expand=True)
    
            # Frame for monthly payments overview
            self.monthly_payments_frame = self.create_monthly_payments_section()
            self.monthly_payments_frame.pack(pady=10, padx=20, fill='both', expand=True)
    
            # Buttons for quick navigation
            button_frame = ttk.Frame(self)
            button_frame.pack(pady=20)
    
            ttk.Button(
                button_frame, text="Add Expense", command=lambda: controller.show_frame(AddExpensePage),
                style='Accent.TButton', padding=10
            ).grid(row=0, column=0, padx=10)
    
            ttk.Button(
                button_frame, text="View Expenses", command=lambda: controller.show_frame(ViewExpensesPage),
                style='Accent.TButton', padding=10
            ).grid(row=0, column=1, padx=10)
    
            ttk.Button(
                button_frame, text="Set Budget", command=lambda: controller.show_frame(SetBudgetPage),
                style='Accent.TButton', padding=10
            ).grid(row=0, column=2, padx=10)
    
        def create_todays_expenses_section(self):
            """Create the section displaying today's expenses."""
            frame = ttk.LabelFrame(self, text="Today's Expenses")
            today = datetime.now().strftime('%Y-%m-%d')
    
            # Fetch today's expenses
            if self.controller.current_user_id:
                expenses = Expense.get_all(self.controller.current_user_id)
                todays_expenses = [exp for exp in expenses if exp[1] == today]
            else:
                todays_expenses = []
    
            if todays_expenses:
                # Group by category
                categories = {}
                for expense in todays_expenses:
                    category = expense[2]
                    amount = expense[3]
                    if category not in categories:
                        categories[category] = 0
                    categories[category] += amount
    
                for category, total in categories.items():
                    ttk.Label(frame, text=f"{category}: ${total:.2f}", style="TLabel").pack(pady=5)
            else:
                ttk.Label(frame, text="No expenses recorded today.", style="TLabel").pack(pady=5)
    
            return frame
    
        def create_todo_list_section(self):
            """Create an editable to-do list section."""
            frame = ttk.LabelFrame(self, text="To-Do List")
    
            self.todo_entry = ttk.Entry(frame)
            self.todo_entry.pack(pady=5, padx=10, fill='x')
    
            # To-do list stored as a simple list of tasks
            self.todo_listbox = tk.Listbox(frame, height=5)
            self.todo_listbox.pack(pady=5, padx=10, fill='x')
    
            # Add, Edit, and Delete buttons for managing the to-do list
            button_frame = ttk.Frame(frame)
            button_frame.pack(pady=5)
    
            ttk.Button(button_frame, text="Add", command=self.add_todo, style='Accent.TButton').grid(row=0, column=0, padx=5)
            ttk.Button(button_frame, text="Edit", command=self.edit_todo, style='Accent.TButton').grid(row=0, column=1, padx=5)
            ttk.Button(button_frame, text="Delete", command=self.delete_todo, style='Accent.TButton').grid(row=0, column=2, padx=5)
    
            return frame
    
        def add_todo(self):
            """Add a new task to the to-do list."""
            task = self.todo_entry.get()
            if task:
                self.todo_listbox.insert(tk.END, task)
                self.todo_entry.delete(0, tk.END)
                logger.info("Added to-do task: %s", task)
            else:
                messagebox.showerror("Input Error", "To-Do task cannot be empty.")
    
        def edit_todo(self):
            """Edit the selected to-do item."""
            try:
                selected_task_index = self.todo_listbox.curselection()[0]
                current_task = self.todo_listbox.get(selected_task_index)
                new_task = simpledialog.askstring("Edit Task", f"Edit task: {current_task}", parent=self)
                if new_task:
                    self.todo_listbox.delete(selected_task_index)
                    self.todo_listbox.insert(selected_task_index, new_task)
                    logger.info("Edited to-do task from '%s' to '%s'", current_task, new_task)
            except IndexError:
                messagebox.showerror("Selection Error", "Please select a task to edit.")
    
        def delete_todo(self):
            """Delete the selected to-do item."""
            try:
                selected_task_index = self.todo_listbox.curselection()[0]
                task = self.todo_listbox.get(selected_task_index)
                self.todo_listbox.delete(selected_task_index)
                logger.info("Deleted to-do task: %s", task)
            except IndexError:
                messagebox.showerror("Selection Error", "Please select a task to delete.")
    
        def create_monthly_payments_section(self):
            """Create a section showing an overview of upcoming monthly payments."""
            frame = ttk.LabelFrame(self, text="Upcoming Monthly Payments")
    
            if self.controller.current_user_id:
                payments = RecurringPayment.get_all(self.controller.current_user_id)
                today = datetime.now().date()
                upcoming_payments = [
                    payment for payment in payments
                    if datetime.strptime(payment[3], '%Y-%m-%d').date() >= today
                ]
            else:
                upcoming_payments = []
    
            if upcoming_payments:
                for payment in upcoming_payments:
                    payment_name = payment[1]
                    due_date = payment[3]
                    amount = payment[2]
                    ttk.Label(frame, text=f"{payment_name}: ${amount:.2f}, Due on {due_date}", style="TLabel").pack(pady=5)
            else:
                ttk.Label(frame, text="No upcoming payments.", style="TLabel").pack(pady=5)
    
            return frame
    
        def refresh(self):
            """
            Refresh the HomePage with the latest data.
    
            Updates today's expenses and upcoming payments sections.
            """
            try:
                # Re-fetch today's expenses and update display
                for widget in self.todays_expenses_frame.winfo_children():
                    widget.destroy()
                today = datetime.now().strftime('%Y-%m-%d')
                if self.controller.current_user_id:
                    expenses = Expense.get_all(self.controller.current_user_id)
                    todays_expenses = [exp for exp in expenses if exp[1] == today]
                else:
                    todays_expenses = []
    
                if todays_expenses:
                    categories = {}
                    for expense in todays_expenses:
                        category = expense[2]
                        amount = expense[3]
                        if category not in categories:
                            categories[category] = 0
                        categories[category] += amount
    
                    for category, total in categories.items():
                        ttk.Label(self.todays_expenses_frame, text=f"{category}: ${total:.2f}", style="TLabel").pack(pady=5)
                else:
                    ttk.Label(self.todays_expenses_frame, text="No expenses recorded today.", style="TLabel").pack(pady=5)
    
                # Re-fetch monthly payments
                for widget in self.monthly_payments_frame.winfo_children():
                    widget.destroy()
                if self.controller.current_user_id:
                    payments = RecurringPayment.get_all(self.controller.current_user_id)
                    today = datetime.now().date()
                    upcoming_payments = [
                        payment for payment in payments
                        if datetime.strptime(payment[3], '%Y-%m-%d').date() >= today
                    ]
                else:
                    upcoming_payments = []
    
                if upcoming_payments:
                    for payment in upcoming_payments:
                        payment_name = payment[1]
                        due_date = payment[3]
                        amount = payment[2]
                        ttk.Label(self.monthly_payments_frame, text=f"{payment_name}: ${amount:.2f}, Due on {due_date}", style="TLabel").pack(pady=5)
                else:
                    ttk.Label(self.monthly_payments_frame, text="No upcoming payments.", style="TLabel").pack(pady=5)
    
                logger.info("HomePage refreshed with latest data.")
            except Exception as e:
                logger.exception("Error in HomePage.refresh: %s", e)
                messagebox.showerror("Error", f"An error occurred while refreshing the dashboard:\n{e}")
    
    
class AddExpensePage(ttk.Frame):
        """Page for adding new expenses."""
    
        def __init__(self, parent, controller):
            """
            Initialize the AddExpensePage.
    
            Args:
                parent (ttk.Frame): The parent frame.
                controller (PersonalBankingApp): The main application controller.
            """
            super().__init__(parent)
            self.controller = controller
    
            ttk.Label(
                self, text="Add New Expense", style='Header.TLabel'
            ).pack(pady=20)
    
            form_frame = ttk.Frame(self)
            form_frame.pack(pady=10)
    
            # Date
            ttk.Label(form_frame, text="Date:").grid(
                row=0, column=0, padx=5, pady=5, sticky='e'
            )
            self.date_entry = CustomDateEntry(form_frame, date_pattern='y-mm-dd')  # Corrected
            self.date_entry.set_date(datetime.today())
            self.date_entry.grid(row=0, column=1, padx=5, pady=5)
    
            # Category
            ttk.Label(form_frame, text="Category:").grid(
                row=1, column=0, padx=5, pady=5, sticky='e'
            )
            self.category_entry = ttk.Combobox(
                form_frame, values=self.get_categories(), width=22, state="readonly"
            )
            self.category_entry.set('')  # Default to empty
            self.category_entry.grid(row=1, column=1, padx=5, pady=5)
    
            # Option to add a new category directly
            ttk.Button(
                form_frame, text="Add New Category", command=lambda: controller.show_frame(CategoryPage), style='TButton'
            ).grid(row=1, column=2, padx=5, pady=5)
    
            # Amount
            ttk.Label(form_frame, text="Amount:").grid(
                row=2, column=0, padx=5, pady=5, sticky='e'
            )
            self.amount_entry = ttk.Entry(form_frame)
            self.amount_entry.grid(row=2, column=1, padx=5, pady=5)
    
            # Buttons
            button_frame = ttk.Frame(self)
            button_frame.pack(pady=20)
    
            ttk.Button(
                button_frame, text="Save Expense", command=self.save_expense, style='Accent.TButton'
            ).grid(row=0, column=0, padx=10)
            ttk.Button(
                button_frame, text="Back to Home", command=lambda: controller.show_frame(HomePage), style='TButton'
            ).grid(row=0, column=1, padx=10)
    
        def get_categories(self):
            """Retrieve categories for the current user."""
            if self.controller.current_user_id:
                categories = Category.get_all(self.controller.current_user_id)
            else:
                categories = []
            return categories
    
        def save_expense(self):
            """Save the new expense to the database."""
            try:
                date_str = self.date_entry.get()  # Now in 'YYYY-MM-DD' format
    
                if not self.controller.current_user_id:
                    messagebox.showerror("Authentication Error", "You must be logged in to add expenses.")
                    return
    
                try:
                    parsed_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                except ValueError:
                    messagebox.showerror("Input Error", "Invalid date format. Use YYYY-MM-DD.")
                    return
    
                category = self.category_entry.get().strip()
                amount_text = self.amount_entry.get().strip()
    
                if not category:
                    messagebox.showerror("Input Error", "Please select a category.")
                    return
    
                # Ensure category exists
                categories = Category.get_all(self.controller.current_user_id)
                if category not in categories:
                    messagebox.showerror("Input Error", f"Category '{category}' does not exist. Please add it first.")
                    return
    
                try:
                    amount = float(amount_text)
                    if amount <= 0:
                        raise ValueError("Amount must be greater than zero.")
                except ValueError as e:
                    messagebox.showerror("Input Error", str(e))
                    return
    
                Expense.add(date_str, category, amount, self.controller.current_user_id)
                messagebox.showinfo("Success", "Expense added successfully.")
                self.clear_entries()
                logger.info("Added new expense: Date=%s, Category=%s, Amount=%.2f, UserID=%s", date_str, category, amount, self.controller.current_user_id)
            except Exception as e:
                logger.exception("Error in save_expense: %s", e)
                messagebox.showerror("Error", f"An error occurred while adding the expense:\n{e}")
    
        def clear_entries(self):
            """Clear the input fields."""
            self.date_entry.set_date(datetime.today())
            self.category_entry.set('')
            self.amount_entry.delete(0, tk.END)
    
        def refresh(self):
            """Refresh category list."""
            try:
                self.category_entry['values'] = self.get_categories()
                logger.info("AddExpensePage categories refreshed.")
            except Exception as e:
                logger.exception("Error in AddExpensePage.refresh: %s", e)
                messagebox.showerror("Error", f"An error occurred while refreshing categories:\n{e}")
    
    
class ViewExpensesPage(ttk.Frame):
        """Page for viewing, editing, and deleting expenses."""
    
        PAGE_SIZE = 20  # Number of expenses per page
    
        def __init__(self, parent, controller):
            """
            Initialize the ViewExpensesPage.
    
            Args:
                parent (ttk.Frame): The parent frame.
                controller (PersonalBankingApp): The main application controller.
            """
            super().__init__(parent)
            self.controller = controller
            self.current_page = 1
            self.total_pages = 1
    
            ttk.Label(
                self, text="View Expenses", style='Header.TLabel'
            ).pack(pady=20)
    
            # Treeview for displaying expenses
            columns = ("ID", "Date", "Category", "Amount")
            self.tree = ttk.Treeview(
                self, columns=columns, show="headings"
            )
            for col in columns:
                self.tree.heading(col, text=col)
                self.tree.column(col, anchor="center", width=100)
            self.tree.pack(padx=10, pady=10, expand=True, fill="both")
    
            # Buttons
            button_frame = ttk.Frame(self)
            button_frame.pack(pady=10)
    
            ttk.Button(
                button_frame, text="Edit Expense", command=self.edit_expense, style='Accent.TButton'
            ).grid(row=0, column=0, padx=10)
            ttk.Button(
                button_frame, text="Delete Expense", command=self.delete_expense, style='Danger.TButton'
            ).grid(row=0, column=1, padx=10)
            ttk.Button(
                button_frame, text="Export to CSV", command=self.export_to_csv, style='Success.TButton'
            ).grid(row=0, column=2, padx=10)
            ttk.Button(
                button_frame, text="Back to Home", command=lambda: controller.show_frame(HomePage), style='TButton'
            ).grid(row=0, column=3, padx=10)
    
            # Pagination Controls
            pagination_frame = ttk.Frame(self)
            pagination_frame.pack(pady=5)
    
            self.prev_button = ttk.Button(
                pagination_frame, text="Previous", command=self.prev_page, style='TButton'
            )
            self.prev_button.grid(row=0, column=0, padx=5)
    
            self.page_label = ttk.Label(pagination_frame, text="Page 1 of 1", style='TLabel')
            self.page_label.grid(row=0, column=1, padx=5)
    
            self.next_button = ttk.Button(
                pagination_frame, text="Next", command=self.next_page, style='TButton'
            )
            self.next_button.grid(row=0, column=2, padx=5)
    
        def refresh(self):
            """
            Refresh the expense list with pagination.
    
            Fetches all expenses, calculates total pages, and displays the first page.
            """
            try:
                if self.controller.current_user_id:
                    expenses = Expense.get_all(self.controller.current_user_id)
                else:
                    expenses = []
                self.total_pages = max(1, (len(expenses) + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
                self.current_page = 1
                self.display_page(expenses)
                logger.info("ViewExpensesPage refreshed. Total pages: %s", self.total_pages)
            except Exception as e:
                logger.exception("Error in ViewExpensesPage.refresh: %s", e)
                messagebox.showerror("Error", f"An error occurred while refreshing expenses:\n{e}")
    
        def display_page(self, expenses):
            """
            Display a specific page of expenses in the Treeview.
    
            Args:
                expenses (list): The complete list of expenses.
            """
            try:
                # Clear the treeview
                for item in self.tree.get_children():
                    self.tree.delete(item)
    
                # Calculate start and end indices
                start_index = (self.current_page - 1) * self.PAGE_SIZE
                end_index = start_index + self.PAGE_SIZE
                page_expenses = expenses[start_index:end_index]
    
                for expense in page_expenses:
                    self.tree.insert("", "end", values=expense)
    
                # Update pagination label
                self.page_label.config(text=f"Page {self.current_page} of {self.total_pages}")
    
                # Enable/disable pagination buttons
                self.prev_button.config(state=tk.NORMAL if self.current_page > 1 else tk.DISABLED)
                self.next_button.config(state=tk.NORMAL if self.current_page < self.total_pages else tk.DISABLED)
    
                logger.info("Displayed page %s of %s.", self.current_page, self.total_pages)
            except Exception as e:
                logger.exception("Error in display_page: %s", e)
                messagebox.showerror("Error", f"An error occurred while displaying expenses:\n{e}")
    
        def next_page(self):
            """Navigate to the next page."""
            try:
                if self.controller.current_user_id:
                    expenses = Expense.get_all(self.controller.current_user_id)
                else:
                    expenses = []
                if self.current_page < self.total_pages:
                    self.current_page += 1
                    self.display_page(expenses)
                    logger.info("Navigated to next page: %s", self.current_page)
            except Exception as e:
                logger.exception("Error in next_page: %s", e)
                messagebox.showerror("Error", f"An error occurred while navigating to the next page:\n{e}")
    
        def prev_page(self):
            """Navigate to the previous page."""
            try:
                if self.controller.current_user_id:
                    expenses = Expense.get_all(self.controller.current_user_id)
                else:
                    expenses = []
                if self.current_page > 1:
                    self.current_page -= 1
                    self.display_page(expenses)
                    logger.info("Navigated to previous page: %s", self.current_page)
            except Exception as e:
                logger.exception("Error in prev_page: %s", e)
                messagebox.showerror("Error", f"An error occurred while navigating to the previous page:\n{e}")
    
        def edit_expense(self):
            """
            Edit the selected expense.
    
            Opens a new window with pre-filled fields for the selected expense.
            """
            try:
                selected_item = self.tree.focus()
                if not selected_item:
                    messagebox.showerror("Selection Error", "Please select an expense to edit.")
                    return
    
                expense_data = self.tree.item(selected_item, "values")
                expense_id, date_str, category, amount = expense_data
    
                # Parse date
                try:
                    date = datetime.strptime(date_str, '%Y-%m-%d').date()
                except ValueError:
                    messagebox.showerror("Input Error", "Invalid date format in selected expense.")
                    return
    
                # Create a new window for editing
                edit_window = tk.Toplevel(self)
                edit_window.title("Edit Expense")
                edit_window.geometry("400x300")
                edit_window.configure(bg="#FFFFFF")
                edit_window.grab_set()  # Make the window modal
    
                ttk.Label(
                    edit_window, text="Edit Expense", style='Header.TLabel'
                ).pack(pady=20)
    
                form_frame = ttk.Frame(edit_window)
                form_frame.pack(pady=10)
    
                # Date
                ttk.Label(form_frame, text="Date:").grid(
                    row=0, column=0, padx=5, pady=5, sticky='e'
                )
                date_entry = CustomDateEntry(form_frame, date_pattern='y-mm-dd')  # Corrected
                date_entry.set_date(date)
                date_entry.grid(row=0, column=1, padx=5, pady=5)
    
                # Category
                ttk.Label(form_frame, text="Category:").grid(
                    row=1, column=0, padx=5, pady=5, sticky='e'
                )
                category_entry = ttk.Combobox(
                    form_frame, values=self.controller.frames[AddExpensePage].get_categories(), width=22, state="readonly"
                )
                category_entry.set(category)
                category_entry.grid(row=1, column=1, padx=5, pady=5)
    
                # Amount
                ttk.Label(form_frame, text="Amount:").grid(
                    row=2, column=0, padx=5, pady=5, sticky='e'
                )
                amount_entry = ttk.Entry(form_frame)
                amount_entry.insert(0, amount)
                amount_entry.grid(row=2, column=1, padx=5, pady=5)
    
                def save_changes():
                    """
                    Save the changes made to the expense.
    
                    Validates inputs and updates the expense in the database.
                    """
                    try:
                        new_date_str = date_entry.get()  # 'YYYY-MM-DD' format
                        try:
                            datetime.strptime(new_date_str, '%Y-%m-%d').date()
                        except ValueError:
                            messagebox.showerror("Input Error", "Invalid date format. Use YYYY-MM-DD.")
                            return
    
                        new_category = category_entry.get().strip()
                        amount_text = amount_entry.get().strip()
    
                        if not new_category:
                            messagebox.showerror("Input Error", "Please select a category.")
                            return
    
                        # Ensure category exists
                        categories = self.controller.frames[AddExpensePage].get_categories()
                        if new_category not in categories:
                            messagebox.showerror("Input Error", f"Category '{new_category}' does not exist. Please add it first.")
                            return
    
                        try:
                            new_amount = float(amount_text)
                            if new_amount <= 0:
                                raise ValueError("Amount must be greater than zero.")
                        except ValueError as e:
                            messagebox.showerror("Input Error", str(e))
                            return
    
                        Expense.update(expense_id, new_date_str, new_category, new_amount)
                        messagebox.showinfo("Success", "Expense updated successfully.")
                        edit_window.destroy()
                        self.refresh()
                        logger.info("Updated expense ID %s: Date=%s, Category=%s, Amount=%.2f", expense_id, new_date_str, new_category, new_amount)
                    except Exception as e:
                        logger.exception("Error in save_changes: %s", e)
                        messagebox.showerror("Error", f"An error occurred while updating the expense:\n{e}")
    
                # Buttons for saving or cancelling changes
                button_frame = ttk.Frame(edit_window)
                button_frame.pack(pady=20)
    
                ttk.Button(button_frame, text="Save Changes", command=save_changes, style='Accent.TButton').grid(
                    row=0, column=0, padx=10
                )
                ttk.Button(button_frame, text="Cancel", command=edit_window.destroy, style='TButton').grid(
                    row=0, column=1, padx=10
                )
            except Exception as e:
                logger.exception("Error in edit_expense: %s", e)
                messagebox.showerror("Error", f"An error occurred while editing the expense:\n{e}")
    
        def delete_expense(self):
            """
            Delete the selected expense.
    
            Prompts the user for confirmation before deletion.
            """
            try:
                selected_item = self.tree.focus()
                if not selected_item:
                    messagebox.showerror("Selection Error", "Please select an expense to delete.")
                    return
    
                expense_id = self.tree.item(selected_item, "values")[0]
                confirm = messagebox.askyesno(
                    "Confirm Delete", "Are you sure you want to delete this expense?"
                )
                if confirm:
                    Expense.delete(expense_id)
                    messagebox.showinfo("Success", "Expense deleted successfully.")
                    self.refresh()
                    logger.info("Deleted expense ID %s.", expense_id)
            except Exception as e:
                logger.exception("Error in delete_expense: %s", e)
                messagebox.showerror("Error", f"An error occurred while deleting the expense:\n{e}")
    
        def export_to_csv(self):
            """
            Export all expenses to a CSV file.
    
            Saves the expenses in 'expenses.csv' in the current directory.
            """
            try:
                if self.controller.current_user_id:
                    expenses = Expense.get_all(self.controller.current_user_id)
                else:
                    expenses = []
                if not expenses:
                    messagebox.showinfo("No Data", "There are no expenses to export.")
                    return
                with open('expenses.csv', 'w', newline='') as file:
                    writer = csv.writer(file)
                    writer.writerow(["ID", "Date", "Category", "Amount"])
                    writer.writerows(expenses)
                messagebox.showinfo("Success", "Expenses exported to expenses.csv.")
                logger.info("Exported expenses to expenses.csv.")
            except Exception as e:
                logger.exception("Error in export_to_csv: %s", e)
                messagebox.showerror("Error", f"An error occurred while exporting expenses:\n{e}")
    
    
class CategoryPage(ttk.Frame):
        """Page for managing expense categories."""
    
        def __init__(self, parent, controller):
            """
            Initialize the CategoryPage.
    
            Args:
                parent (ttk.Frame): The parent frame.
                controller (PersonalBankingApp): The main application controller.
            """
            super().__init__(parent)
            self.controller = controller
    
            ttk.Label(
                self, text="Manage Categories", style='Header.TLabel'
            ).pack(pady=20)
    
            form_frame = ttk.Frame(self)
            form_frame.pack(pady=10)
    
            ttk.Label(form_frame, text="New Category Name:").grid(
                row=0, column=0, padx=5, pady=5, sticky='e'
            )
            self.category_entry = ttk.Entry(form_frame)
            self.category_entry.grid(row=0, column=1, padx=5, pady=5)
    
            ttk.Button(
                self, text="Add Category", command=self.add_category, style='Accent.TButton'
            ).pack(pady=10)
    
            # List of Categories
            self.category_listbox = tk.Listbox(self, height=10)
            self.category_listbox.pack(pady=10, fill="both", expand=True)
    
            # Delete Button
            ttk.Button(
                self, text="Delete Selected Category", command=self.delete_category, style='Danger.TButton'
            ).pack(pady=5)
    
        def refresh(self):
            """Refresh the category list."""
            try:
                self.category_listbox.delete(0, tk.END)
                if self.controller.current_user_id:
                    categories = Category.get_all(self.controller.current_user_id)
                else:
                    categories = []
                for category in categories:
                    self.category_listbox.insert(tk.END, category)
                logger.info("CategoryPage refreshed with latest categories.")
            except Exception as e:
                logger.exception("Error in CategoryPage.refresh: %s", e)
                messagebox.showerror("Error", f"An error occurred while refreshing categories:\n{e}")
    
        def add_category(self):
            """Add a new category."""
            try:
                name = self.category_entry.get().strip()
                
                if name:
                    Category.add(name)
                    messagebox.showinfo("Success", f"Category '{name}' added.")
                    self.category_entry.delete(0, tk.END)
                    self.refresh()
                    # Also refresh categories in AddExpensePage if it's open
                    self.controller.frames[AddExpensePage].refresh()
                    logger.info("Added new category: %s", name)
                else:
                    messagebox.showerror("Input Error", "Category name cannot be empty.")
            except ValueError as ve:
                messagebox.showerror("Input Error", str(ve))
                logger.warning("Attempted to add duplicate category: %s", name)
            except Exception as e:
                logger.exception("Error in add_category: %s", e)
                messagebox.showerror("Error", f"An error occurred while adding the category:\n{e}")
    
        def delete_category(self):
            """
            Delete the selected category.
    
            Prompts the user for confirmation before deletion.
            """
            try:
                selected_indices = self.category_listbox.curselection()
                if not selected_indices:
                    messagebox.showerror("Selection Error", "Please select a category to delete.")
                    return
                selected_category = self.category_listbox.get(selected_indices[0])
                confirm = messagebox.askyesno(
                    "Confirm Delete", f"Are you sure you want to delete the category '{selected_category}'?"
                )
                if confirm:
                    Category.delete(selected_category)
                    messagebox.showinfo("Success", f"Category '{selected_category}' deleted.")
                    self.refresh()
                    # Also refresh categories in AddExpensePage if it's open
                    self.controller.frames[AddExpensePage].refresh()
                    logger.info("Deleted category: %s", selected_category)
            except Exception as e:
                logger.exception("Error in delete_category: %s", e)
                messagebox.showerror("Error", f"An error occurred while deleting the category:\n{e}")
    
    
class RecurringPaymentsPage(ttk.Frame):
        """Page for managing recurring payments."""
    
        def __init__(self, parent, controller):
            """
            Initialize the RecurringPaymentsPage.
    
            Args:
                parent (ttk.Frame): The parent frame.
                controller (PersonalBankingApp): The main application controller.
            """
            super().__init__(parent)
            self.controller = controller
    
            ttk.Label(
                self, text="Manage Recurring Payments", style='Header.TLabel'
            ).pack(pady=20)
    
            form_frame = ttk.Frame(self)
            form_frame.pack(pady=10)
    
            # Name
            ttk.Label(form_frame, text="Payment Name:").grid(
                row=0, column=0, padx=5, pady=5, sticky='e'
            )
            self.name_entry = ttk.Entry(form_frame)
            self.name_entry.grid(row=0, column=1, padx=5, pady=5)
    
            # Amount
            ttk.Label(form_frame, text="Amount:").grid(
                row=1, column=0, padx=5, pady=5, sticky='e'
            )
            self.amount_entry = ttk.Entry(form_frame)
            self.amount_entry.grid(row=1, column=1, padx=5, pady=5)
    
            # Due Date
            ttk.Label(form_frame, text="Due Date:").grid(
                row=2, column=0, padx=5, pady=5, sticky='e'
            )
            self.due_date_entry = CustomDateEntry(form_frame, date_pattern='y-mm-dd')  # Corrected
            self.due_date_entry.set_date(datetime.today())
            self.due_date_entry.grid(row=2, column=1, padx=5, pady=5)
    
            # Frequency
            ttk.Label(form_frame, text="Frequency:").grid(
                row=3, column=0, padx=5, pady=5, sticky='e'
            )
            self.frequency_entry = ttk.Combobox(
                form_frame, values=["Weekly", "Monthly", "Yearly"], state="readonly"
            )
            self.frequency_entry.grid(row=3, column=1, padx=5, pady=5)
    
            ttk.Button(
                self, text="Add Payment", command=self.add_payment, style='Accent.TButton'
            ).pack(pady=10)
    
            # Treeview for displaying recurring payments
            columns = ("ID", "Name", "Amount", "Due Date", "Frequency")
            self.tree = ttk.Treeview(
                self, columns=columns, show="headings"
            )
            for col in columns:
                self.tree.heading(col, text=col)
                self.tree.column(col, anchor="center", width=100)
            self.tree.pack(padx=10, pady=10, expand=True, fill="both")
    
            # Buttons
            button_frame = ttk.Frame(self)
            button_frame.pack(pady=5)
    
            ttk.Button(
                button_frame, text="Mark as Paid", command=self.mark_as_paid, style='Warning.TButton'
            ).grid(row=0, column=0, padx=10)
            ttk.Button(
                button_frame, text="Delete Payment", command=self.delete_payment, style='Danger.TButton'
            ).grid(row=0, column=1, padx=10)
    
        def refresh(self):
            """Refresh the list of recurring payments."""
            try:
                for item in self.tree.get_children():
                    self.tree.delete(item)
                if self.controller.current_user_id:
                    payments = RecurringPayment.get_all(self.controller.current_user_id)
                else:
                    payments = []
                for payment in payments:
                    self.tree.insert("", "end", values=payment)
                logger.info("RecurringPaymentsPage refreshed with latest payments.")
            except Exception as e:
                logger.exception("Error in RecurringPaymentsPage.refresh: %s", e)
                messagebox.showerror("Error", f"An error occurred while refreshing recurring payments:\n{e}")
    
        def add_payment(self):
            """Add a new recurring payment."""
            try:
                name = self.name_entry.get().strip()
                amount_text = self.amount_entry.get().strip()
                due_date_str = self.due_date_entry.get()
                frequency = self.frequency_entry.get()
    
                if not name or not frequency:
                    messagebox.showerror("Input Error", "Please fill all the fields.")
                    return
    
                try:
                    amount = float(amount_text)
                    if amount <= 0:
                        raise ValueError("Amount must be greater than zero.")
                except ValueError as e:
                    messagebox.showerror("Input Error", str(e))
                    return
    
                # Validate due_date_str
                try:
                    datetime.strptime(due_date_str, '%Y-%m-%d').date()
                except ValueError:
                    messagebox.showerror("Input Error", "Invalid date format. Use YYYY-MM-DD.")
                    return
    
                RecurringPayment.add(name, amount, due_date_str, frequency, self.controller.current_user_id)
                messagebox.showinfo("Success", f"Recurring payment '{name}' added.")
                self.clear_entries()
                self.refresh()
                logger.info("Added new recurring payment: Name=%s, Amount=%.2f, Due Date=%s, Frequency=%s, UserID=%s", name, amount, due_date_str, frequency, self.controller.current_user_id)
            except Exception as e:
                logger.exception("Error in add_payment: %s", e)
                messagebox.showerror("Error", f"An error occurred while adding the recurring payment:\n{e}")
    
        def clear_entries(self):
            """Clear the input fields."""
            self.name_entry.delete(0, tk.END)
            self.amount_entry.delete(0, tk.END)
            self.due_date_entry.set_date(datetime.today())
            self.frequency_entry.set('')
    
        def delete_payment(self):
            """
            Delete the selected recurring payment.
    
            Prompts the user for confirmation before deletion.
            """
            try:
                selected_item = self.tree.focus()
                if not selected_item:
                    messagebox.showerror(
                        "Selection Error", "Please select a payment to delete."
                    )
                    return
    
                payment_id = self.tree.item(selected_item, "values")[0]
                confirm = messagebox.askyesno(
                    "Confirm Delete", "Are you sure you want to delete this payment?"
                )
                if confirm:
                    RecurringPayment.delete(payment_id)
                    messagebox.showinfo("Success", "Payment deleted successfully.")
                    self.refresh()
                    logger.info("Deleted recurring payment ID %s.", payment_id)
            except Exception as e:
                logger.exception("Error in delete_payment: %s", e)
                messagebox.showerror("Error", f"An error occurred while deleting the recurring payment:\n{e}")
    
        def mark_as_paid(self):
            """
            Mark the selected payment as paid and update its due date.
    
            Updates the due date based on the frequency after marking as paid.
            """
            try:
                selected_item = self.tree.focus()
                if not selected_item:
                    messagebox.showerror(
                        "Selection Error", "Please select a payment to mark as paid."
                    )
                    return
    
                payment_id = self.tree.item(selected_item, "values")[0]
                payment_date_str = datetime.now().strftime('%Y-%m-%d')
                RecurringPayment.mark_as_paid(payment_id, payment_date_str)
                messagebox.showinfo("Success", "Payment marked as paid.")
                self.refresh()
                logger.info("Marked recurring payment ID %s as paid.", payment_id)
            except Exception as e:
                logger.exception("Error in mark_as_paid: %s", e)
                messagebox.showerror("Error", f"An error occurred while marking the payment as paid:\n{e}")
    
    
class SpendingSummaryPage(ttk.Frame):
        """Page for displaying spending summaries and charts."""
    
        def __init__(self, parent, controller):
            """
            Initialize the SpendingSummaryPage.
    
            Args:
                parent (ttk.Frame): The parent frame.
                controller (PersonalBankingApp): The main application controller.
            """
            super().__init__(parent)
            self.controller = controller
    
            ttk.Label(
                self, text="Spending Summary", style='Header.TLabel'
            ).pack(pady=20)
    
            self.summary_frame = ttk.Frame(self)
            self.summary_frame.pack(pady=10)
    
            # Labels for summaries
            self.daily_label = ttk.Label(self.summary_frame, text="", style='TLabel')
            self.daily_label.pack(pady=5)
    
            self.weekly_label = ttk.Label(self.summary_frame, text="", style='TLabel')
            self.weekly_label.pack(pady=5)
    
            self.monthly_label = ttk.Label(self.summary_frame, text="", style='TLabel')
            self.monthly_label.pack(pady=5)
    
            self.yearly_label = ttk.Label(self.summary_frame, text="", style='TLabel')
            self.yearly_label.pack(pady=5)
    
            # Chart Area
            self.chart_frame = ttk.Frame(self)
            self.chart_frame.pack(pady=20, fill='both', expand=True)
    
        def refresh(self):
            """
            Update the spending summaries and charts.
    
            Calculates spending over different periods and updates the display.
            """
            try:
                if not self.controller.current_user_id:
                    # No user logged in
                    self.daily_label.config(text="Today's Spending: $0.00")
                    self.weekly_label.config(text="This Week's Spending: $0.00")
                    self.monthly_label.config(text="This Month's Spending: $0.00")
                    self.yearly_label.config(text="This Year's Spending: $0.00")
    
                    for widget in self.chart_frame.winfo_children():
                        widget.destroy()
                    ttk.Label(
                        self.chart_frame, text="No spending data to display.", style='TLabel'
                    ).pack(pady=20)
                    return
    
                today = datetime.now().date()
                start_of_day = today.strftime('%Y-%m-%d')
                start_of_week = (today - timedelta(days=today.weekday())).strftime('%Y-%m-%d')
                start_of_month = today.replace(day=1).strftime('%Y-%m-%d')
                start_of_year = today.replace(month=1, day=1).strftime('%Y-%m-%d')
    
                daily_spending = Expense.get_spending_since(start_of_day, self.controller.current_user_id)
                weekly_spending = Expense.get_spending_since(start_of_week, self.controller.current_user_id)
                monthly_spending = Expense.get_spending_since(start_of_month, self.controller.current_user_id)
                yearly_spending = Expense.get_spending_since(start_of_year, self.controller.current_user_id)
    
                self.daily_label.config(text=f"Today's Spending: ${daily_spending:.2f}")
                self.weekly_label.config(text=f"This Week's Spending: ${weekly_spending:.2f}")
                self.monthly_label.config(text=f"This Month's Spending: ${monthly_spending:.2f}")
                self.yearly_label.config(text=f"This Year's Spending: ${yearly_spending:.2f}")
    
                # Update Chart
                for widget in self.chart_frame.winfo_children():
                    widget.destroy()
    
                data = Expense.get_daily_spending(self.controller.current_user_id)
                if data:
                    dates = [datetime.strptime(record[0], '%Y-%m-%d').date() for record in data]
                    amounts = [record[1] for record in data]
    
                    fig, ax = plt.subplots(figsize=(8, 4))
                    ax.plot(dates, amounts, marker='o', linestyle='-')
                    ax.set_title('Spending Over Time')
                    ax.set_xlabel('Date')
                    ax.set_ylabel('Amount ($)')
                    fig.autofmt_xdate()
    
                    canvas = FigureCanvasTkAgg(fig, master=self.chart_frame)
                    canvas.draw()
                    canvas.get_tk_widget().pack(fill='both', expand=True)
                    logger.info("SpendingSummaryPage chart updated.")
                else:
                    ttk.Label(
                        self.chart_frame, text="No spending data to display.", style='TLabel'
                    ).pack(pady=20)
                    logger.info("SpendingSummaryPage has no spending data to display.")
            except Exception as e:
                logger.exception("Error in SpendingSummaryPage.refresh: %s", e)
                messagebox.showerror("Error", f"An error occurred while refreshing the spending summary:\n{e}")
    
    
class SetBudgetPage(ttk.Frame):
        """Page for setting the monthly budget."""
    
        def __init__(self, parent, controller):
            """
            Initialize the SetBudgetPage.
    
            Args:
                parent (ttk.Frame): The parent frame.
                controller (PersonalBankingApp): The main application controller.
            """
            super().__init__(parent)
            self.controller = controller
    
            ttk.Label(
                self, text="Set Monthly Budget", style='Header.TLabel'
            ).pack(pady=20)
    
            form_frame = ttk.Frame(self)
            form_frame.pack(pady=10)
    
            # Month
            ttk.Label(form_frame, text="Month (YYYY-MM):").grid(
                row=0, column=0, padx=5, pady=5, sticky='e'
            )
            self.month_entry = ttk.Entry(form_frame)
            current_month = datetime.now().strftime('%Y-%m')
            self.month_entry.insert(0, current_month)
            self.month_entry.grid(row=0, column=1, padx=5, pady=5)
    
            # Amount
            ttk.Label(form_frame, text="Budget Amount:").grid(
                row=1, column=0, padx=5, pady=5, sticky='e'
            )
            self.amount_entry = ttk.Entry(form_frame)
            self.amount_entry.grid(row=1, column=1, padx=5, pady=5)
    
            # Buttons
            button_frame = ttk.Frame(self)
            button_frame.pack(pady=20)
    
            ttk.Button(
                button_frame, text="Set Budget", command=self.set_budget, style='Accent.TButton'
            ).grid(row=0, column=0, padx=10)
            ttk.Button(
                button_frame, text="Back to Home", command=lambda: controller.show_frame(HomePage), style='TButton'
            ).grid(row=0, column=1, padx=10)
    
        def set_budget(self):
            """Set the monthly budget."""
            try:
                month = self.month_entry.get().strip()
                amount_text = self.amount_entry.get().strip()
    
                if not self.controller.current_user_id:
                    messagebox.showerror("Authentication Error", "You must be logged in to set a budget.")
                    return
    
                # Validate month format
                try:
                    datetime.strptime(month, '%Y-%m')
                except ValueError:
                    messagebox.showerror("Input Error", "Invalid month format. Use YYYY-MM.")
                    return
    
                # Validate amount
                try:
                    amount = float(amount_text)
                    if amount <= 0:
                        raise ValueError("Budget amount must be greater than zero.")
                except ValueError as e:
                    messagebox.showerror("Input Error", str(e))
                    return
    
                Budget.set_monthly_budget(month, amount, self.controller.current_user_id)
                messagebox.showinfo("Success", f"Budget for {month} set to ${amount:.2f}.")
                self.clear_entries()
                logger.info("Set budget for %s: Amount=%.2f, UserID=%s", month, amount, self.controller.current_user_id)
            except Exception as e:
                logger.exception("Error in set_budget: %s", e)
                messagebox.showerror("Error", f"An error occurred while setting the budget:\n{e}")
    
        def clear_entries(self):
            """Clear the input fields."""
            try:
                current_month = datetime.now().strftime('%Y-%m')
                self.month_entry.delete(0, tk.END)
                self.month_entry.insert(0, current_month)
                self.amount_entry.delete(0, tk.END)
                logger.info("Cleared budget input fields.")
            except Exception as e:
                logger.exception("Error in clear_entries: %s", e)
                messagebox.showerror("Error", f"An error occurred while clearing the budget fields:\n{e}")
    
        def refresh(self):
            """Refresh the page."""
            self.clear_entries()
            logger.info("SetBudgetPage refreshed.")
    
    
if __name__ == "__main__":
    app = PersonalBankingApp()
    app.mainloop()
