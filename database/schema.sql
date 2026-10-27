-- Kenya Airways conversational agent: PostgreSQL schema
-- Implements the ERD in Chapter 4 (Users, Flights, Bookings, Conversations).
-- Re-runnable: drops and recreates all tables.

DROP TABLE IF EXISTS auth_sessions;
DROP TABLE IF EXISTS conversations;
DROP TABLE IF EXISTS bookings;
DROP TABLE IF EXISTS flights;
DROP TABLE IF EXISTS users;

CREATE TABLE users (
    user_id      SERIAL PRIMARY KEY,
    name         VARCHAR(100) NOT NULL,
    email        VARCHAR(150) NOT NULL UNIQUE,
    booking_ref  VARCHAR(20),
    -- scrypt hash 'scrypt$n$r$p$salt$hash'; NULL means the account cannot log in
    password_hash VARCHAR(255),
    role         VARCHAR(20)  NOT NULL DEFAULT 'passenger'
                 CHECK (role IN ('passenger', 'admin')),
    created_at   TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE TABLE flights (
    flight_id        SERIAL PRIMARY KEY,
    flight_number    VARCHAR(10)  NOT NULL,
    origin           VARCHAR(100) NOT NULL,
    destination      VARCHAR(100) NOT NULL,
    departure_time   TIMESTAMP    NOT NULL,
    arrival_time     TIMESTAMP    NOT NULL,
    status           VARCHAR(20)  NOT NULL DEFAULT 'on_time'
                     CHECK (status IN ('on_time', 'delayed', 'cancelled', 'departed', 'landed')),
    seats_available  INTEGER      NOT NULL DEFAULT 0 CHECK (seats_available >= 0),
    CHECK (arrival_time > departure_time),
    UNIQUE (flight_number, departure_time)
);

CREATE TABLE bookings (
    booking_ref  VARCHAR(20) PRIMARY KEY,
    user_id      INTEGER     NOT NULL REFERENCES users (user_id) ON DELETE CASCADE,
    flight_id    INTEGER     NOT NULL REFERENCES flights (flight_id),
    -- Name of the traveller when it differs from the account holder (bookings made in the chat)
    passenger_name VARCHAR(100),
    status       VARCHAR(20) NOT NULL DEFAULT 'confirmed'
                 CHECK (status IN ('confirmed', 'cancelled', 'checked_in')),
    created_at   TIMESTAMP   NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMP   NOT NULL DEFAULT NOW()
);

-- One row per chat session. sender_id is the session id the chat widget sends to Rasa;
-- user_id is filled in once the passenger is identified via a booking reference.
CREATE TABLE conversations (
    conversation_id  SERIAL PRIMARY KEY,
    sender_id        VARCHAR(100) NOT NULL UNIQUE,
    user_id          INTEGER      REFERENCES users (user_id) ON DELETE SET NULL,
    start_time       TIMESTAMP    NOT NULL DEFAULT NOW(),
    end_time         TIMESTAMP,
    turn_count       INTEGER      NOT NULL DEFAULT 0,
    last_intent      VARCHAR(50),
    status           VARCHAR(20)  NOT NULL DEFAULT 'active'
                     CHECK (status IN ('active', 'closed', 'escalated'))
);

-- Indexes on the columns the dialogue actions query most often
CREATE INDEX idx_flights_flight_number ON flights (flight_number);
CREATE INDEX idx_flights_route_departure ON flights (LOWER(origin), LOWER(destination), departure_time);
CREATE INDEX idx_bookings_user_id ON bookings (user_id);
CREATE INDEX idx_bookings_flight_id ON bookings (flight_id);
CREATE INDEX idx_conversations_user_id ON conversations (user_id);

-- Web portal login sessions (FR-06, NFR-06). Only a SHA-256 hash of the
-- session token is stored, so a leaked table cannot be replayed as cookies.
CREATE TABLE auth_sessions (
    token_hash  CHAR(64)  PRIMARY KEY,
    user_id     INTEGER   NOT NULL REFERENCES users (user_id) ON DELETE CASCADE,
    created_at  TIMESTAMP NOT NULL DEFAULT NOW(),
    expires_at  TIMESTAMP NOT NULL
);
CREATE INDEX idx_auth_sessions_user_id ON auth_sessions (user_id);
