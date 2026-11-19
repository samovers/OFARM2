-- Disposable conformance storage. Applied only by the test service administrator.
CREATE SCHEMA claim_evidence;
CREATE TABLE claim_evidence.guard (
    tenant uuid NOT NULL, key text NOT NULL, version int NOT NULL DEFAULT 1, PRIMARY KEY (tenant, key)
);
CREATE TABLE claim_evidence.source (
    tenant uuid NOT NULL, ref text NOT NULL, revision text NOT NULL, body bytea NOT NULL, PRIMARY KEY (tenant, ref)
);
CREATE TABLE claim_evidence.member (
    tenant uuid NOT NULL, set_key text NOT NULL, position int NOT NULL, ref text NOT NULL,
    PRIMARY KEY (tenant, set_key, position), UNIQUE (tenant, set_key, ref)
);
CREATE TABLE claim_evidence.claim_id (tenant uuid NOT NULL, id text NOT NULL, PRIMARY KEY (tenant, id));
CREATE TABLE claim_evidence.attempt (
    tenant uuid NOT NULL, id uuid NOT NULL, selection bytea NOT NULL,
    status text NOT NULL DEFAULT 'registered' CHECK (status IN ('registered','started','completed','aborted','refused','unknown')),
    PRIMARY KEY (tenant, id)
);
CREATE TABLE claim_evidence.observation (
    tenant uuid NOT NULL, id uuid NOT NULL, body bytea NOT NULL,
    PRIMARY KEY (tenant, id), FOREIGN KEY (tenant, id) REFERENCES claim_evidence.attempt (tenant, id)
);
GRANT USAGE ON SCHEMA claim_evidence TO ofarm_app, ofarm_worker;
GRANT SELECT ON claim_evidence.guard, claim_evidence.source, claim_evidence.member, claim_evidence.claim_id
    TO ofarm_app, ofarm_worker;
-- PostgreSQL also needs an UPDATE privilege to lock a row FOR SHARE.
GRANT UPDATE(version) ON claim_evidence.guard TO ofarm_app, ofarm_worker;
GRANT INSERT ON claim_evidence.observation TO ofarm_app, ofarm_worker;
DO $fixture$
DECLARE relation text;
BEGIN
    FOREACH relation IN ARRAY ARRAY['guard','source','member','claim_id','observation'] LOOP
        EXECUTE format('ALTER TABLE claim_evidence.%I ENABLE ROW LEVEL SECURITY', relation);
        EXECUTE format('CREATE POLICY bound_tenant ON claim_evidence.%I
            USING (tenant = ofarm.current_tenant_id()) WITH CHECK (tenant = ofarm.current_tenant_id())', relation);
    END LOOP;
END;
$fixture$;
