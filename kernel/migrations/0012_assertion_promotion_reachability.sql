-- Decision ASSERTION-PROMOTION-429 v3. Keep the sealed v0.1 graph guards.
-- The runner holds the table locks through the history check and installation.
DO $migration$
DECLARE
    predecessor pg_catalog.record;
    assertion_count pg_catalog.int8;
    matching_count pg_catalog.int8;
BEGIN
    IF (SELECT pg_catalog.encode(
                   pg_catalog.sha256(pg_catalog.convert_to(routine.prosrc, 'UTF8')),
                   'hex'
               )
          FROM pg_catalog.pg_proc AS routine
         WHERE routine.oid = 'ofarm.verify_tenant_structure()'::pg_catalog.regprocedure
       ) IS DISTINCT FROM 'a4cbb2588a2850123836103f5f095ad94a51ddb7d4ed58a4852fd9b864fb016e' THEN
        RAISE EXCEPTION USING ERRCODE = '55000',
            MESSAGE = 'version-11 tenant verifier source differs';
    END IF;

    SELECT * INTO STRICT predecessor FROM ofarm.verify_tenant_structure();
    IF predecessor.structurally_compatible IS DISTINCT FROM true
       OR predecessor.difference_count IS DISTINCT FROM 0
       OR predecessor.migration_head_version IS DISTINCT FROM 11
       OR predecessor.migration_row_count IS DISTINCT FROM 11
       OR predecessor.applied_prefix_digest IS DISTINCT FROM
            'sha256:9d4f8716e4b547b449c7d312ab738ca04048fa4cc7a75d048cc77e1bb1e0e672'
       OR predecessor.structural_catalog_digest IS DISTINCT FROM
            'sha256:b3e64cd17e288f5753793230cc45da7dd316c374114c9475bc735ce03c1aff51' THEN
        RAISE EXCEPTION USING ERRCODE = '55000',
            MESSAGE = 'version-11 tenant structure differs';
    END IF;

    LOCK TABLE ofarm.kernel_record, ofarm.kernel_edge IN ACCESS EXCLUSIVE MODE;
    IF (SELECT pg_catalog.count(*)
          FROM pg_catalog.pg_class AS relation
         WHERE relation.oid IN ('ofarm.kernel_record'::pg_catalog.regclass,
                                'ofarm.kernel_edge'::pg_catalog.regclass)
           AND relation.relrowsecurity AND relation.relforcerowsecurity) <> 2 THEN
        RAISE EXCEPTION USING ERRCODE = '55000',
            MESSAGE = 'version-11 ledger row security differs';
    END IF;

    ALTER TABLE ofarm.kernel_record NO FORCE ROW LEVEL SECURITY;
    ALTER TABLE ofarm.kernel_edge NO FORCE ROW LEVEL SECURITY;

    <<verify_history_visibility>>
    BEGIN
        IF CURRENT_USER <> 'ofarm_owner' OR (
            SELECT pg_catalog.count(*)
              FROM pg_catalog.pg_class AS relation
              JOIN pg_catalog.pg_namespace AS namespace
                ON namespace.oid = relation.relnamespace
             WHERE namespace.nspname = 'ofarm'
               AND relation.relname IN ('kernel_record', 'kernel_edge')
               AND relation.relkind = 'r'
               AND pg_catalog.pg_get_userbyid(relation.relowner) = CURRENT_USER
               AND relation.relrowsecurity AND NOT relation.relforcerowsecurity
               AND NOT pg_catalog.row_security_active(relation.oid)
        ) <> 2 THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
                MESSAGE = 'v0.2 promotion history visibility is incomplete';
        END IF;
    END verify_history_visibility;

    -- The checked partial unique index permits at most one promotion link per
    -- tenant and destination. Each left join therefore preserves one assertion.
    SELECT pg_catalog.count(*), pg_catalog.count(trace.record_id)
      INTO assertion_count, matching_count
      FROM ofarm.kernel_record AS assertion
      LEFT JOIN ofarm.kernel_edge AS edge
        ON edge.tenant_id = assertion.tenant_id
       AND edge.dst_record_id = assertion.record_id
       AND edge.edge_kind = 'PROMOTION_EMITS'
       AND edge.batch_id = assertion.batch_id
       AND edge.batch_full_xid = assertion.batch_full_xid
      LEFT JOIN ofarm.kernel_record AS trace
        ON trace.tenant_id = edge.tenant_id
       AND trace.record_id = edge.src_record_id
       AND trace.record_kind = 'ofarm.promotiontrace.v0.1'
       AND trace.batch_id = edge.batch_id
       AND trace.batch_full_xid = edge.batch_full_xid
       AND pg_catalog.jsonb_typeof(trace.payload -> 'emittedAssertionRecordRefs') = 'array'
       AND (trace.payload -> 'emittedAssertionRecordRefs') OPERATOR(pg_catalog.?)
                assertion.record_id::pg_catalog.text
     WHERE assertion.record_kind = 'ofarm.assertionrecord.v0.2';
    IF matching_count <> assertion_count THEN
        RAISE EXCEPTION USING ERRCODE = '55000',
            MESSAGE = 'v0.2 promotion history contains incomplete proof',
            DETAIL = pg_catalog.format('assessed %s, matched %s, exceptions %s',
                        assertion_count, matching_count, assertion_count - matching_count);
    END IF;
    RAISE NOTICE 'v0.2 promotion history assessed %, matched %, exceptions 0',
        assertion_count, matching_count;

    ALTER TABLE ofarm.kernel_record FORCE ROW LEVEL SECURITY;
    ALTER TABLE ofarm.kernel_edge FORCE ROW LEVEL SECURITY;
    IF (SELECT pg_catalog.count(*)
          FROM pg_catalog.pg_class AS relation
         WHERE relation.oid IN ('ofarm.kernel_record'::pg_catalog.regclass,
                                'ofarm.kernel_edge'::pg_catalog.regclass)
           AND relation.relrowsecurity AND relation.relforcerowsecurity) <> 2 THEN
        RAISE EXCEPTION USING ERRCODE = '55000',
            MESSAGE = 'ledger row security was not restored';
    END IF;
END
$migration$;

CREATE FUNCTION ofarm.require_assertion_v02_promotion()
RETURNS pg_catalog.trigger
LANGUAGE plpgsql VOLATILE PARALLEL UNSAFE SECURITY INVOKER
SET search_path = pg_catalog, pg_temp
AS $body$
BEGIN
    -- The existing edge trigger checks the trace kind and both endpoints'
    -- provenance. This check requires the edge and the typed assertion reference.
    IF NOT EXISTS (
        SELECT 1
          FROM ofarm.kernel_edge AS edge
          JOIN ofarm.kernel_record AS trace
            ON trace.tenant_id = edge.tenant_id AND trace.record_id = edge.src_record_id
         WHERE edge.tenant_id = NEW.tenant_id
           AND edge.dst_record_id = NEW.record_id
           AND edge.edge_kind = 'PROMOTION_EMITS'
           AND edge.batch_id = NEW.batch_id
           AND edge.batch_full_xid = NEW.batch_full_xid
           AND pg_catalog.jsonb_typeof(trace.payload -> 'emittedAssertionRecordRefs') = 'array'
           AND (trace.payload -> 'emittedAssertionRecordRefs') OPERATOR(pg_catalog.?)
                    NEW.record_id::pg_catalog.text
    ) THEN
        RAISE EXCEPTION USING ERRCODE = '23514',
            MESSAGE = 'v0.2 assertion lacks matching promotion proof';
    END IF;
    RETURN NULL;
END
$body$;

REVOKE ALL PRIVILEGES ON FUNCTION ofarm.require_assertion_v02_promotion() FROM PUBLIC;
CREATE CONSTRAINT TRIGGER kernel_record_require_assertion_v02_promotion
AFTER INSERT ON ofarm.kernel_record
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW WHEN (NEW.record_kind = 'ofarm.assertionrecord.v0.2')
EXECUTE FUNCTION ofarm.require_assertion_v02_promotion();

-- Advance only the authenticated predecessor's head, graph-trigger inventory
-- and complete catalog fingerprint. The runner checks the successor after it
-- appends row 12; the fingerprint excludes only the verifier's own source.
DO $migration$
DECLARE
    definition pg_catalog.text := pg_catalog.pg_get_functiondef(
        'ofarm.verify_tenant_structure()'::pg_catalog.regprocedure
    );
    change pg_catalog.record;
BEGIN
    FOR change IN SELECT * FROM (VALUES
        ('observed_migration_count <> 11', 'observed_migration_count <> 12'),
        ('observed_head_version <> 11', 'observed_head_version <> 12'),
        ('pg_catalog.max(migration.applied_prefix_digest) FILTER (WHERE migration.version = 11)',
         'pg_catalog.max(migration.applied_prefix_digest) FILTER (WHERE migration.version = 12)'),
        ($old$                'kernel_record_require_promotion'$old$,
         $new$                'kernel_record_require_promotion',
                'kernel_record_require_assertion_v02_promotion'$new$),
        ('graph_constraint_count <> 2', 'graph_constraint_count <> 3'),
        ('sha256:b3e64cd17e288f5753793230cc45da7dd316c374114c9475bc735ce03c1aff51',
         'sha256:c114062966a5e6a27366cb254ace0e4ba79ef35e57732302341a4fa991b586cc')
    ) AS replacements(old_text, new_text)
    LOOP
        IF pg_catalog.cardinality(pg_catalog.string_to_array(definition, change.old_text)) <> 2
           OR pg_catalog.strpos(definition, change.new_text) <> 0 THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
                MESSAGE = 'version-11 tenant verifier definition differs';
        END IF;
        definition := pg_catalog.replace(definition, change.old_text, change.new_text);
    END LOOP;
    EXECUTE definition;
END
$migration$;
