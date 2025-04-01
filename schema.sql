CREATE TABLE Users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL
);

CREATE TABLE Pills (
    pill_id INTEGER PRIMARY KEY AUTOINCREMENT,
    color TEXT NOT NULL
);

CREATE TABLE UserPlans (
    plan_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    day_of_week TEXT NOT NULL,
    time_day TEXT NOT NULL, -- morning, noon, evening, night
    pill_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES Users(user_id),
    FOREIGN KEY (pill_id) REFERENCES Pills(pill_id)
);