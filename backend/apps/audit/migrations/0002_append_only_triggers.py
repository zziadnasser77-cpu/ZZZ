from django.db import migrations

SQL_UP = """
CREATE OR REPLACE FUNCTION audit_events_immutable() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_auditevent is append-only (% blocked)', TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_events_no_update_delete
BEFORE UPDATE OR DELETE ON audit_auditevent
FOR EACH ROW EXECUTE FUNCTION audit_events_immutable();

CREATE TRIGGER audit_events_no_truncate
BEFORE TRUNCATE ON audit_auditevent
FOR EACH STATEMENT EXECUTE FUNCTION audit_events_immutable();
"""
SQL_DOWN = """
DROP TRIGGER IF EXISTS audit_events_no_truncate ON audit_auditevent;
DROP TRIGGER IF EXISTS audit_events_no_update_delete ON audit_auditevent;
DROP FUNCTION IF EXISTS audit_events_immutable();
"""


class Migration(migrations.Migration):
    dependencies = [("audit", "0001_initial")]
    operations = [migrations.RunSQL(SQL_UP, SQL_DOWN)]
