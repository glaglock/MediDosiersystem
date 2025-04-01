import sqlite3
from flask import Flask, render_template, request, url_for, flash, redirect
from werkzeug.exceptions import abort

def get_db_connection(): 
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def get_user(user_id):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE user_id = ?',
                        (user_id,)).fetchone()
    conn.close()
    if user is None:
        abort(404)
    return user

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your secret key' 

@app.route('/')
def index():
    conn = get_db_connection()
    users = conn.execute('SELECT * FROM Users').fetchall()
    conn.close()
    return render_template('index.html', users=users)


@app.route('/createUser', methods=('GET', 'POST'))
def createUser():
    if request.method == 'POST': 
        name = request.form['name']

        conn = get_db_connection()
        cursor = conn.cursor()

        # Insert user 
        cursor.execute('INSERT INTO users (name) VALUES (?)', (name,))
        user_id = cursor.lastrowid

        # Ensure pill types exist and get their IDs
        pill_colors = ['red', 'blue', 'green', 'yellow']
        pill_ids = {}
        for color in pill_colors:
            cursor.execute('INSERT OR IGNORE INTO Pills (color) VALUES (?)', (color,))
            cursor.execute('SELECT pill_id FROM Pills WHERE color = ?', (color,))
            pill_ids[color] = cursor.fetchone()['pill_id']

        # Insert user plans
        days_of_week = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        times_of_day = ['morning', 'noon', 'evening', 'night']
        for day in days_of_week:
            for time in times_of_day:
                for color in pill_colors:
                    quantity = request.form.get(f'{day}_{time}_{color}', 0)
                    if quantity:
                        cursor.execute('''
                            INSERT INTO UserPlans (user_id, day_of_week, time_day, pill_id, quantity)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (user_id, day, time, pill_ids[color], quantity))
        
        conn.commit()
        conn.close()
        
        return redirect(url_for('index'))
    return render_template('createUser.html')

@app.route("/displayUser/<int:user_id>")
def displayUser(user_id):
    user = get_user(user_id)
    conn = get_db_connection()
    user_plans_raw = conn.execute('''
        SELECT day_of_week, time_day, Pills.color, UserPlans.quantity
        FROM UserPlans
        JOIN Pills ON UserPlans.pill_id = Pills.pill_id
        WHERE UserPlans.user_id = ?
    ''', (user_id,)).fetchall()
    conn.close()

    # Structure the user_plans data
    user_plans = {day: {time: {'red': 0, 'blue': 0, 'green': 0, 'yellow': 0} for time in ['Morning', 'Noon', 'Evening', 'Night']} for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']}
    time_mapping = {
        'morning': 'Morning',
        'noon': 'Noon',
        'evening': 'Evening',
        'night': 'Night'
    }
    for plan in user_plans_raw:
        day = plan['day_of_week']
        time = time_mapping.get(plan['time_day'].lower(), plan['time_day'])
        color = plan['color']
        quantity = plan['quantity']
        user_plans[day][time][color] = quantity

    return render_template('displayUser.html', user=user, user_plans=user_plans)

@app.route('/deleteUser/<int:user_id>', methods=['POST', 'GET'])
def deleteUser(user_id): 
    conn = get_db_connection()
    conn.execute('DELETE FROM users WHERE user_id = ?', (user_id,))
    conn.execute('DELETE FROM UserPlans WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
    flash('User was successfully deleted!')
    return redirect(url_for('index'))


@app.route('/editUser/<int:user_id>', methods=['GET', 'POST'])
def editUser(user_id):
    user = get_user(user_id)  # Fetch user details
    conn = get_db_connection()

    if request.method == 'POST':
        # Update user name
        name = request.form['name']
        conn.execute('UPDATE Users SET name = ? WHERE user_id = ?', (name, user_id))

        # Update pill schedule
        pill_colors = ['red', 'blue', 'green', 'yellow']
        days_of_week = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        times_of_day = ['morning', 'noon', 'evening', 'night']

        for day in days_of_week:
            for time in times_of_day:
                for color in pill_colors:
                    quantity = request.form.get(f'{day}_{time}_{color}', 0)
                    conn.execute('''
                        UPDATE UserPlans
                        SET quantity = ?
                        WHERE user_id = ? AND day_of_week = ? AND time_day = ? AND pill_id = (
                            SELECT pill_id FROM Pills WHERE color = ?
                        )
                    ''', (quantity, user_id, day, time, color))

        conn.commit()
        conn.close()
        return redirect(url_for('displayUser', user_id=user_id))

    # Fetch user plans for pre-filling the form
    user_plans_raw = conn.execute('''
        SELECT day_of_week, time_day, Pills.color, UserPlans.quantity
        FROM UserPlans
        JOIN Pills ON UserPlans.pill_id = Pills.pill_id
        WHERE UserPlans.user_id = ?
    ''', (user_id,)).fetchall()
    conn.close()

    # Structure user plans for the template
    user_plans = {day: {time: {'red': 0, 'blue': 0, 'green': 0, 'yellow': 0} for time in ['Morning', 'Noon', 'Evening', 'Night']} for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']}
    time_mapping = {
        'morning': 'Morning',
        'noon': 'Noon',
        'evening': 'Evening',
        'night': 'Night'
    }
    for plan in user_plans_raw:
        day = plan['day_of_week']
        time = time_mapping.get(plan['time_day'].lower(), plan['time_day'])
        color = plan['color']
        quantity = plan['quantity']
        user_plans[day][time][color] = quantity

    return render_template('editUser.html', user=user, user_plans=user_plans)


















