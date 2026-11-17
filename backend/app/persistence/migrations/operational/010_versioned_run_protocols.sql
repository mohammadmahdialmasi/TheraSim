ALTER TABLE simulation_runs
ADD COLUMN protocol_id TEXT NOT NULL DEFAULT 'ACT_EDUCATIONAL_SIMULATION'
CHECK (length(protocol_id) > 0);

ALTER TABLE simulation_runs
ADD COLUMN protocol_version TEXT NOT NULL DEFAULT '0.1'
CHECK (length(protocol_version) > 0);

ALTER TABLE simulation_runs
ADD COLUMN session_planning_policy TEXT NOT NULL DEFAULT 'flexible'
CHECK (
    session_planning_policy IN (
        'flexible',
        'goal_based',
        'milestone_based',
        'open_ended'
    )
);

ALTER TABLE simulation_runs
ADD COLUMN evaluation_rubric_id TEXT NOT NULL DEFAULT 'ACT_RUBRIC_V0'
CHECK (length(evaluation_rubric_id) > 0);

ALTER TABLE simulation_runs
ADD COLUMN evaluation_rubric_version TEXT NOT NULL DEFAULT '0.2'
CHECK (length(evaluation_rubric_version) > 0);

CREATE TRIGGER simulation_run_configuration_is_immutable
BEFORE UPDATE OF
    case_id,
    case_version_id,
    modality,
    language,
    configuration_version,
    protocol_id,
    protocol_version,
    session_planning_policy,
    evaluation_rubric_id,
    evaluation_rubric_version
ON simulation_runs
FOR EACH ROW
WHEN NEW.case_id IS NOT OLD.case_id
  OR NEW.case_version_id IS NOT OLD.case_version_id
  OR NEW.modality IS NOT OLD.modality
  OR NEW.language IS NOT OLD.language
  OR NEW.configuration_version IS NOT OLD.configuration_version
  OR NEW.protocol_id IS NOT OLD.protocol_id
  OR NEW.protocol_version IS NOT OLD.protocol_version
  OR NEW.session_planning_policy IS NOT OLD.session_planning_policy
  OR NEW.evaluation_rubric_id IS NOT OLD.evaluation_rubric_id
  OR NEW.evaluation_rubric_version IS NOT OLD.evaluation_rubric_version
BEGIN
    SELECT RAISE(ABORT, 'simulation_run_configuration_is_immutable');
END;
