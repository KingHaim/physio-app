PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;
CREATE TABLE alembic_version (
	version_num VARCHAR(32) NOT NULL, 
	CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);
INSERT INTO alembic_version VALUES('6589efa087c4');
CREATE TABLE patient (
	id INTEGER NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	date_of_birth DATE, 
	contact VARCHAR(100), 
	diagnosis VARCHAR(200), 
	treatment_plan TEXT, 
	notes TEXT, 
	status VARCHAR(20), 
	created_at DATETIME, 
	updated_at DATETIME, 
	email VARCHAR(100), 
	phone VARCHAR(20), 
	address_line1 VARCHAR(100), 
	address_line2 VARCHAR(100), 
	city VARCHAR(50), 
	postcode VARCHAR(20), 
	preferred_location VARCHAR(50), 
	PRIMARY KEY (id)
);
CREATE TABLE practice_reports (
	id INTEGER NOT NULL, 
	content TEXT NOT NULL, 
	generated_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE patient_reports (
	id INTEGER NOT NULL, 
	patient_id INTEGER NOT NULL, 
	content TEXT NOT NULL, 
	generated_date DATETIME, 
	report_type VARCHAR(50), 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patient (id)
);
CREATE TABLE recurring_appointment (
	id INTEGER NOT NULL, 
	patient_id INTEGER NOT NULL, 
	start_date DATE NOT NULL, 
	end_date DATE, 
	recurrence_type VARCHAR(50) NOT NULL, 
	time_of_day TIME NOT NULL, 
	treatment_type VARCHAR(150) NOT NULL, 
	notes TEXT, 
	location VARCHAR(100), 
	provider VARCHAR(100), 
	fee_charged FLOAT, 
	is_active BOOLEAN NOT NULL, 
	payment_method VARCHAR(50), 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patient (id)
);
CREATE TABLE treatment (
	id INTEGER NOT NULL, 
	patient_id INTEGER NOT NULL, 
	treatment_type VARCHAR(100) NOT NULL, 
	assessment TEXT, 
	notes TEXT, 
	status VARCHAR(50), 
	provider VARCHAR(100), 
	created_at DATETIME, 
	updated_at DATETIME, 
	body_chart_url VARCHAR(255), 
	pain_level INTEGER, 
	movement_restriction VARCHAR(50), 
	evaluation_data JSON, 
	location VARCHAR(100), 
	visit_type VARCHAR(50), 
	fee_charged FLOAT, 
	payment_method VARCHAR(50), 
	calendly_invitee_uri VARCHAR(255), 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patient (id)
);
CREATE TABLE unmatched_calendly_booking (
	id INTEGER NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	email VARCHAR(100) NOT NULL, 
	event_type VARCHAR(100), 
	start_time DATETIME, 
	calendly_invitee_id VARCHAR(100), 
	status VARCHAR(20), 
	matched_patient_id INTEGER, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(matched_patient_id) REFERENCES patient (id)
);
CREATE TABLE user (
	id INTEGER NOT NULL, 
	username VARCHAR(64), 
	email VARCHAR(120) NOT NULL, 
	password_hash VARCHAR(256), 
	is_admin BOOLEAN, 
	created_at DATETIME, 
	"plan" VARCHAR(50) NOT NULL, 
	role VARCHAR(20) NOT NULL, 
	patient_id INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patient (id)
);
CREATE TABLE trigger_point (
	id INTEGER NOT NULL, 
	treatment_id INTEGER NOT NULL, 
	location_x FLOAT NOT NULL, 
	location_y FLOAT NOT NULL, 
	type VARCHAR(50), 
	muscle VARCHAR(100), 
	intensity INTEGER, 
	symptoms TEXT, 
	referral_pattern TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(treatment_id) REFERENCES treatment (id)
);
CREATE UNIQUE INDEX ix_treatment_calendly_invitee_uri ON treatment (calendly_invitee_uri);
CREATE UNIQUE INDEX ix_user_email ON user (email);
CREATE UNIQUE INDEX ix_user_username ON user (username);
COMMIT;
