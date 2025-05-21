import sqlite3
import paho.mqtt.client as mqtt 
import json
from flask import Flask, render_template, request, url_for, flash, redirect
from werkzeug.exceptions import abort


# MQTT Setup 
#MQTT_BROKER = "localhost" # for local communication 
MQTT_BROKER = "192.168.178.157" # for ESP32 comm 
MQTT_PORT = 1883 
MQTT_TOPIC_PUBLISH = "esp32/pills"      # Channel where esp32 listens 
MQTT_TOPIC_SUBSCRIBE = "raspy/updates" 


#Initialize MQTT client 
mqtt_client = mqtt.Client() 


def on_connect(client, userdata, flags, rc): 
    if rc == 0: 
        print("Connected to MQTT Broker!")
        client.subscribe(MQTT_TOPIC_SUBSCRIBE) 
    else: 
        print(f"Failed to connect, return code {rc}") 

def on_message(client, userdata, msg): 
    print(f"Received message on {msg.topic}:{msg.payload.decode()}") 
    process_mqtt_message(client, userdata, msg) 
    
    
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message 
mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60) 
mqtt_client.loop_start() 




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
        
        user_schedule = []
        
        # Insert user plans
        days_of_week = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        times_of_day = ['morning', 'noon', 'evening', 'night']
        for day in days_of_week:
            for time in times_of_day:
                pill_data = {}
                for color in pill_colors:
                    quantity = request.form.get(f'{day}_{time}_{color}', 0)
                
                    #if quantity > 0: 
                        #pill_data[color] = quantity 
                                    
                    if quantity:
                        cursor.execute('''
                            INSERT INTO UserPlans (user_id, day_of_week, time_day, pill_id, quantity)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (user_id, day, time, pill_ids[color], quantity))
                                        
                  
                        user_schedule.append({
                            "day": day, 
                            "time": time, 
                            "color": color, 
                            "quantity" : int(quantity)
                            })
                          
                               
        
        
        # Publish to MQTT 
        mqtt_message = json.dumps({
        #"action": "create", 
        "user_id": user_id, 
        "name": name,
        "schedule": user_schedule
        })
        
        
        
        print(f"Publishing to {MQTT_TOPIC_PUBLISH}: {mqtt_message}") 
        mqtt_client.publish(MQTT_TOPIC_PUBLISH, mqtt_message)
        
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



def process_mqtt_message(client, userdata, msg):
    try:
        # Nachricht vom MQTT-Kanal auslesen
        payload = msg.payload.decode('utf-8')
        print(f"process Received message on {msg.topic}: {payload}")

        # JSON-Daten aus der Nachricht extrahieren
        data = json.loads(payload)
        name = data.get('name')
        day_of_week = data.get('day')
        
        print(f"Name: {name}") 
        print(f"day: {day_of_week}")

        if not name or not day_of_week:
            print("Invalid message: 'name' or 'day' is missing.")
            return

        # Verbindung zur Datenbank herstellen
        conn = get_db_connection()

        # Benutzer-ID anhand des Namens abrufen
        user = conn.execute('SELECT user_id FROM Users WHERE name = ?', (name,)).fetchone()
        if not user:
            print(f"User with name '{name}' not found.")
            conn.close()
            return

        user_id = user['user_id']

        # Tablettenanzahl für den angegebenen Wochentag abrufen
        pill_schedule = conn.execute('''
            SELECT time_day, Pills.color, UserPlans.quantity
            FROM UserPlans
            JOIN Pills ON UserPlans.pill_id = Pills.pill_id
            WHERE UserPlans.user_id = ? AND UserPlans.day_of_week = ?
        ''', (user_id, day_of_week)).fetchall()

        conn.close()

        # Strukturieren der Daten für die Tageszeiten
        #schedule = {
         #   'Morning': {'red': 1, 'blue': 1, 'green': 1, 'yellow': 1},
          #  'Noon': {'red': 0, 'blue': 0, 'green': 0, 'yellow': 0},
           # 'Evening': {'red': 0, 'blue': 0, 'green': 0, 'yellow': 0},
            #'Night': {'red': 0, 'blue': 0, 'green': 0, 'yellow': 0}
        #}
        
        schedule = []
        
        

        # Daten aus der Datenbank in die Struktur einfügen
        #for entry in pill_schedule:
         #   time = entry['time_day']
          #  color = entry['color']
           # quantity = entry['quantity']
            #if time in schedule:
             #   schedule[time][color] = quantity
                
                
        for entry in pill_schedule: 
            schedule.append({
                "time": entry['time_day'], 
                "color": entry['color'], 
                "quantity": entry['quantity']
                })

        # Ergebnisse ausgeben
        #print(f"Pill schedule for {name} on {day_of_week}:")
        #for time, pills in schedule.items():
         #   print(f"  {time}: {pills}")
            
        
        print(f"Pill schedule for {name} on {day_of_week}. {schedule}")

        # Nachricht für den ESP32 vorbereiten
        mqtt_message = json.dumps({
            "name": name,
            "day": day_of_week,
            "schedule": schedule
        })

        # Nachricht auf den MQTT-Kanal veröffentlichen
        MQTT_TOPIC_SCHEDULE = "esp32/pills"
        print(f"Publishing to {MQTT_TOPIC_SCHEDULE}: {mqtt_message}")
        mqtt_client.publish(MQTT_TOPIC_SCHEDULE, mqtt_message)

    except json.JSONDecodeError:
        print("Failed to decode JSON from the message.")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__": 
    app.run(host="0.0.0.0", port=5000)














