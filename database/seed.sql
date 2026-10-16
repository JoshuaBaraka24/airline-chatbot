-- Sample data for demonstrating all four support domains.
-- Departure dates are relative to the day the seed is loaded, so the demo
-- always has upcoming flights. Re-run database/init_db.py to refresh them.

TRUNCATE auth_sessions, conversations, bookings, flights, users RESTART IDENTITY CASCADE;

INSERT INTO users (name, email, booking_ref) VALUES
    ('John Mwangi',   'john@email.com',  'BK001'),
    ('Amina Hassan',  'amina@email.com', 'BK002'),
    ('Peter Kamau',   'peter@email.com', 'BK003'),
    ('Grace Wanjiku', 'grace@email.com', 'BK004'),
    ('David Ochieng', 'david@email.com', 'BK005'),
    ('Mary Atieno',   'mary@email.com',  'BK006');

-- Staff account for the admin dashboard. Passwords for all demo accounts are
-- set by database/init_db.py, because hashing happens in Python.
INSERT INTO users (name, email, role) VALUES
    ('KQ Support Admin', 'admin@kq-demo.local', 'admin');

INSERT INTO flights (flight_number, origin, destination, departure_time, arrival_time, status, seats_available)
SELECT f.flight_number, f.origin, f.destination,
       CURRENT_DATE + f.day_offset + f.dep_time,
       CURRENT_DATE + f.day_offset + f.dep_time + f.duration,
       f.status, f.seats
FROM (VALUES
    ('KQ101', 'Nairobi',  'Mombasa',      6, TIME '08:00', INTERVAL '1 hour',         'on_time',   42),
    ('KQ101', 'Nairobi',  'Mombasa',      7, TIME '08:00', INTERVAL '1 hour',         'on_time',   18),
    ('KQ101', 'Nairobi',  'Mombasa',      9, TIME '08:00', INTERVAL '1 hour',         'on_time',   60),
    ('KQ601', 'Mombasa',  'Nairobi',      6, TIME '11:00', INTERVAL '1 hour',         'on_time',   35),
    ('KQ601', 'Mombasa',  'Nairobi',      8, TIME '11:00', INTERVAL '1 hour',         'on_time',   50),
    ('KQ202', 'Nairobi',  'Dubai',        7, TIME '22:00', INTERVAL '5 hours',        'delayed',   12),
    ('KQ202', 'Nairobi',  'Dubai',        9, TIME '22:00', INTERVAL '5 hours',        'on_time',   40),
    ('KQ305', 'Nairobi',  'London',       8, TIME '23:30', INTERVAL '9 hours',        'on_time',   25),
    ('KQ305', 'Nairobi',  'London',      15, TIME '23:30', INTERVAL '9 hours',        'on_time',   70),
    ('KQ450', 'Nairobi',  'Amsterdam',    9, TIME '01:00', INTERVAL '8 hours 30 minutes', 'on_time', 30),
    ('KQ505', 'Nairobi',  'Johannesburg', 10, TIME '09:00', INTERVAL '4 hours',       'cancelled',  0),
    ('KQ505', 'Nairobi',  'Johannesburg', 12, TIME '09:00', INTERVAL '4 hours',       'on_time',   55),
    ('KQ702', 'Nairobi',  'Kisumu',       7, TIME '07:00', INTERVAL '1 hour',         'on_time',   20),
    ('KQ702', 'Nairobi',  'Kisumu',       9, TIME '07:00', INTERVAL '1 hour',         'on_time',   45),
    ('KQ789', 'Nairobi',  'Lagos',       11, TIME '14:00', INTERVAL '6 hours',        'on_time',   33)
) AS f(flight_number, origin, destination, day_offset, dep_time, duration, status, seats);

-- Each booking points at the earliest departure of its flight number
INSERT INTO bookings (booking_ref, user_id, flight_id, status)
SELECT b.booking_ref, b.user_id,
       (SELECT flight_id FROM flights
         WHERE flight_number = b.flight_number
         ORDER BY departure_time LIMIT 1),
       b.status
FROM (VALUES
    ('BK001', 1, 'KQ101', 'confirmed'),
    ('BK002', 2, 'KQ202', 'confirmed'),
    ('BK003', 3, 'KQ305', 'confirmed'),
    ('BK004', 4, 'KQ450', 'checked_in'),
    ('BK005', 5, 'KQ505', 'confirmed'),
    ('BK006', 6, 'KQ702', 'cancelled')
) AS b(booking_ref, user_id, flight_number, status);
