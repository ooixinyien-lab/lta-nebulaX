CREATE TABLE IF NOT EXISTS audit_events (
	id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	actor VARCHAR(255) NOT NULL, 
	action VARCHAR(128) NOT NULL, 
	entity_type VARCHAR(64) NOT NULL, 
	entity_id VARCHAR(64) NOT NULL, 
	detail JSON, 
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS instances (
	id VARCHAR(64) NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	fingerprint VARCHAR(64) NOT NULL, 
	created_by VARCHAR(255) NOT NULL, 
	status VARCHAR(32) NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (fingerprint)
);

CREATE TABLE IF NOT EXISTS instance_revisions (
	id VARCHAR(64) NOT NULL, 
	instance_id VARCHAR(64) NOT NULL, 
	revision_number INTEGER NOT NULL, 
	input_fingerprint VARCHAR(64) NOT NULL, 
	parser_version VARCHAR(64) NOT NULL, 
	validation_status VARCHAR(32) NOT NULL, 
	validation_errors JSON, 
	created_by VARCHAR(255) NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (instance_id, revision_number), 
	FOREIGN KEY(instance_id) REFERENCES instances (id)
);

CREATE TABLE IF NOT EXISTS instance_activities (
	activity_id VARCHAR(64) NOT NULL, 
	contract_number VARCHAR(64) NOT NULL, 
	activity_type VARCHAR(64) NOT NULL, 
	start_location_id VARCHAR(128) NOT NULL, 
	end_location_id VARCHAR(128) NOT NULL, 
	total_accesses INTEGER NOT NULL, 
	planned_start_date DATE NOT NULL, 
	predecessor_activity_id VARCHAR(64), 
	activity_priority INTEGER NOT NULL, 
	revision_id VARCHAR(64) NOT NULL, 
	PRIMARY KEY (activity_id, revision_id), 
	FOREIGN KEY(revision_id) REFERENCES instance_revisions (id)
);

CREATE INDEX IF NOT EXISTS ix_activity_revision_contract ON instance_activities (revision_id, contract_number);

CREATE TABLE IF NOT EXISTS instance_buffer_rules (
	nature_of_works VARCHAR(64) NOT NULL, 
	up_to_buffer_sectors INTEGER NOT NULL, 
	opposite_bound_required BOOLEAN NOT NULL, 
	revision_id VARCHAR(64) NOT NULL, 
	PRIMARY KEY (nature_of_works, revision_id), 
	FOREIGN KEY(revision_id) REFERENCES instance_revisions (id)
);

CREATE TABLE IF NOT EXISTS instance_contracts (
	contract_number VARCHAR(64) NOT NULL, 
	contract_description TEXT NOT NULL, 
	contract_award_date DATE NOT NULL, 
	activity_type VARCHAR(64) NOT NULL, 
	nature_of_activity VARCHAR(64) NOT NULL, 
	contract_priority INTEGER NOT NULL, 
	contract_completion_date DATE NOT NULL, 
	planned_completion_date DATE NOT NULL, 
	number_of_workfronts INTEGER NOT NULL, 
	access_type VARCHAR(16) NOT NULL, 
	number_of_maximum_access_per_week INTEGER NOT NULL, 
	revision_id VARCHAR(64) NOT NULL, 
	PRIMARY KEY (contract_number, revision_id), 
	FOREIGN KEY(revision_id) REFERENCES instance_revisions (id)
);

CREATE TABLE IF NOT EXISTS instance_files (
	revision_id VARCHAR(64) NOT NULL, 
	file_type VARCHAR(32) NOT NULL, 
	original_filename VARCHAR(255) NOT NULL, 
	storage_key VARCHAR(1024) NOT NULL, 
	sha256 VARCHAR(64) NOT NULL, 
	size_bytes INTEGER NOT NULL, 
	PRIMARY KEY (revision_id, file_type), 
	FOREIGN KEY(revision_id) REFERENCES instance_revisions (id)
);

CREATE TABLE IF NOT EXISTS instance_lines (
	line_code VARCHAR(32) NOT NULL, 
	line_name VARCHAR(255) NOT NULL, 
	revision_id VARCHAR(64) NOT NULL, 
	PRIMARY KEY (line_code, revision_id), 
	FOREIGN KEY(revision_id) REFERENCES instance_revisions (id)
);

CREATE TABLE IF NOT EXISTS instance_locations (
	location_id VARCHAR(128) NOT NULL, 
	location_kind VARCHAR(64) NOT NULL, 
	line_code VARCHAR(32) NOT NULL, 
	bound VARCHAR(16) NOT NULL, 
	supply_capacity INTEGER NOT NULL, 
	revision_id VARCHAR(64) NOT NULL, 
	PRIMARY KEY (location_id, revision_id), 
	FOREIGN KEY(revision_id) REFERENCES instance_revisions (id)
);

CREATE TABLE IF NOT EXISTS instance_parameters (
	"key" VARCHAR(64) NOT NULL, 
	value VARCHAR(255) NOT NULL, 
	revision_id VARCHAR(64) NOT NULL, 
	PRIMARY KEY ("key", revision_id), 
	FOREIGN KEY(revision_id) REFERENCES instance_revisions (id)
);

CREATE TABLE IF NOT EXISTS instance_sectors (
	sector_id VARCHAR(128) NOT NULL, 
	line_code VARCHAR(32) NOT NULL, 
	from_station_id VARCHAR(64) NOT NULL, 
	to_station_id VARCHAR(64) NOT NULL, 
	seq INTEGER NOT NULL, 
	is_shared BOOLEAN NOT NULL, 
	revision_id VARCHAR(64) NOT NULL, 
	PRIMARY KEY (sector_id, revision_id), 
	FOREIGN KEY(revision_id) REFERENCES instance_revisions (id)
);

CREATE TABLE IF NOT EXISTS instance_stations (
	line_code VARCHAR(32) NOT NULL, 
	station_id VARCHAR(64) NOT NULL, 
	seq INTEGER NOT NULL, 
	is_interchange BOOLEAN NOT NULL, 
	revision_id VARCHAR(64) NOT NULL, 
	PRIMARY KEY (line_code, station_id, revision_id), 
	FOREIGN KEY(revision_id) REFERENCES instance_revisions (id)
);

CREATE TABLE IF NOT EXISTS solver_runs (
	id VARCHAR(64) NOT NULL, 
	revision_id VARCHAR(64) NOT NULL, 
	scenario VARCHAR(1) NOT NULL, 
	baseline_run_id VARCHAR(64), 
	status VARCHAR(32) NOT NULL, 
	phase VARCHAR(32), 
	requested_time_limit FLOAT NOT NULL, 
	solver_version VARCHAR(128), 
	validator_version VARCHAR(128), 
	workload_complete BOOLEAN NOT NULL, 
	incumbent_score FLOAT, 
	error_message TEXT, 
	started_at DATETIME, 
	finished_at DATETIME, 
	created_by VARCHAR(255) NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(revision_id) REFERENCES instance_revisions (id)
);

CREATE INDEX IF NOT EXISTS ix_solver_runs_revision ON solver_runs (revision_id, scenario);

CREATE TABLE IF NOT EXISTS plans (
	id VARCHAR(64) NOT NULL, 
	revision_id VARCHAR(64) NOT NULL, 
	scenario VARCHAR(1) NOT NULL, 
	base_run_id VARCHAR(64), 
	status VARCHAR(16) NOT NULL, 
	version INTEGER NOT NULL, 
	created_by VARCHAR(255) NOT NULL, 
	published_by VARCHAR(255), 
	published_at DATETIME, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(revision_id) REFERENCES instance_revisions (id), 
	FOREIGN KEY(base_run_id) REFERENCES solver_runs (id)
);

CREATE INDEX IF NOT EXISTS ix_plans_revision ON plans (revision_id, scenario, status);

CREATE TABLE IF NOT EXISTS run_accesses (
	run_id VARCHAR(64) NOT NULL, 
	activity_id VARCHAR(64) NOT NULL, 
	access_seq INTEGER NOT NULL, 
	week INTEGER NOT NULL, 
	eclo BOOLEAN NOT NULL, 
	access_night INTEGER NOT NULL, 
	PRIMARY KEY (run_id, activity_id, access_seq), 
	FOREIGN KEY(run_id) REFERENCES solver_runs (id)
);

CREATE TABLE IF NOT EXISTS run_artifacts (
	run_id VARCHAR(64) NOT NULL, 
	artifact_type VARCHAR(64) NOT NULL, 
	storage_key VARCHAR(1024) NOT NULL, 
	sha256 VARCHAR(64) NOT NULL, 
	content_type VARCHAR(128) NOT NULL, 
	PRIMARY KEY (run_id, artifact_type), 
	FOREIGN KEY(run_id) REFERENCES solver_runs (id)
);

CREATE TABLE IF NOT EXISTS run_contract_results (
	run_id VARCHAR(64) NOT NULL, 
	scenario VARCHAR(1) NOT NULL, 
	contract_number VARCHAR(64) NOT NULL, 
	simulated_completion_date DATE NOT NULL, 
	overrun_days INTEGER NOT NULL, 
	PRIMARY KEY (run_id, contract_number), 
	FOREIGN KEY(run_id) REFERENCES solver_runs (id)
);

CREATE TABLE IF NOT EXISTS run_occupancies (
	run_id VARCHAR(64) NOT NULL, 
	activity_id VARCHAR(64) NOT NULL, 
	week INTEGER NOT NULL, 
	location_id VARCHAR(128) NOT NULL, 
	co_share_group VARCHAR(128) NOT NULL, 
	PRIMARY KEY (run_id, activity_id, week, location_id), 
	FOREIGN KEY(run_id) REFERENCES solver_runs (id)
);

CREATE INDEX IF NOT EXISTS ix_run_occupancy_location ON run_occupancies (run_id, week, location_id);

CREATE TABLE IF NOT EXISTS run_validation_reports (
	run_id VARCHAR(64) NOT NULL, 
	provenance VARCHAR(128) NOT NULL, 
	local_checks_passed BOOLEAN NOT NULL, 
	rule_results JSON NOT NULL, 
	score_components JSON, 
	PRIMARY KEY (run_id), 
	FOREIGN KEY(run_id) REFERENCES solver_runs (id)
);

CREATE TABLE IF NOT EXISTS plan_accesses (
	plan_id VARCHAR(64) NOT NULL, 
	activity_id VARCHAR(64) NOT NULL, 
	access_seq INTEGER NOT NULL, 
	week INTEGER NOT NULL, 
	eclo BOOLEAN NOT NULL, 
	access_night INTEGER NOT NULL, 
	PRIMARY KEY (plan_id, activity_id, access_seq), 
	FOREIGN KEY(plan_id) REFERENCES plans (id)
);

CREATE TABLE IF NOT EXISTS plan_change_events (
	id INTEGER NOT NULL, 
	plan_id VARCHAR(64) NOT NULL, 
	version INTEGER NOT NULL, 
	actor VARCHAR(255) NOT NULL, 
	action VARCHAR(64) NOT NULL, 
	detail JSON, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(plan_id) REFERENCES plans (id)
);

CREATE TABLE IF NOT EXISTS plan_occupancies (
	plan_id VARCHAR(64) NOT NULL, 
	activity_id VARCHAR(64) NOT NULL, 
	week INTEGER NOT NULL, 
	location_id VARCHAR(128) NOT NULL, 
	co_share_group VARCHAR(128) NOT NULL, 
	PRIMARY KEY (plan_id, activity_id, week, location_id), 
	FOREIGN KEY(plan_id) REFERENCES plans (id)
);

CREATE TABLE IF NOT EXISTS explanation_fact_packs (
	id VARCHAR(64) NOT NULL, 
	instance_id VARCHAR(64) NOT NULL, 
	instance_revision_id VARCHAR(64) NOT NULL, 
	run_id VARCHAR(64) NOT NULL, 
	baseline_run_id VARCHAR(64), 
	activity_id VARCHAR(64) NOT NULL, 
	facts_json JSON NOT NULL, 
	fallback_summary TEXT NOT NULL, 
	evidence_hash VARCHAR(64) NOT NULL, 
	builder_version VARCHAR(64) NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(instance_id) REFERENCES instances (id), 
	FOREIGN KEY(instance_revision_id) REFERENCES instance_revisions (id), 
	FOREIGN KEY(run_id) REFERENCES solver_runs (id)
);

CREATE INDEX IF NOT EXISTS ix_explanation_fact_packs_lookup ON explanation_fact_packs (run_id, activity_id);

CREATE TABLE IF NOT EXISTS chat_sessions (
	id VARCHAR(64) NOT NULL, 
	instance_id VARCHAR(64) NOT NULL, 
	run_id VARCHAR(64) NOT NULL, 
	baseline_run_id VARCHAR(64), 
	created_by VARCHAR(255) NOT NULL, 
	created_at DATETIME NOT NULL, 
	last_activity_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(instance_id) REFERENCES instances (id), 
	FOREIGN KEY(run_id) REFERENCES solver_runs (id)
);

CREATE INDEX IF NOT EXISTS ix_chat_sessions_user ON chat_sessions (created_by, last_activity_at);

CREATE TABLE IF NOT EXISTS chat_turns (
	id VARCHAR(64) NOT NULL, 
	session_id VARCHAR(64) NOT NULL, 
	user_id VARCHAR(255) NOT NULL, 
	question_redacted TEXT NOT NULL, 
	answer_redacted TEXT NOT NULL, 
	response_mode VARCHAR(32) NOT NULL, 
	provider VARCHAR(64), 
	model VARCHAR(64), 
	prompt_template_version VARCHAR(64), 
	fact_pack_id VARCHAR(64), 
	tool_trace_json JSON, 
	citation_json JSON, 
	uncertainty_json JSON, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(session_id) REFERENCES chat_sessions (id)
);

CREATE INDEX IF NOT EXISTS ix_chat_turns_session ON chat_turns (session_id, created_at);
