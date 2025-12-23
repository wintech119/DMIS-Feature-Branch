/*
  DMIS - Last Mile (Beneficiaries) Migration v2
  Works with existing tables from prior migration, adds missing columns and constraints

  Goals:
  - Rename existing columns to match new standard naming (warehouse_tier -> tier_code)
  - Add custodian_kind constraint
  - Add allow_lastmile_issue to warehouse
  - Extend transaction table for beneficiary/audit linkage
*/

BEGIN;

SET LOCAL lock_timeout = '10s';
SET LOCAL statement_timeout = '5min';

-- -------------------------------------------------------------------
-- 1) RETIRE/DROP LEGACY HSA TABLE(S) IF THEY EXIST (SAFE)
-- -------------------------------------------------------------------
DO $$
DECLARE
  dep_cnt int;
  new_name text;
BEGIN
  IF to_regclass('public.hsa') IS NOT NULL THEN
    SELECT COUNT(*)
      INTO dep_cnt
      FROM pg_constraint c
      WHERE c.contype = 'f'
        AND c.confrelid = 'public.hsa'::regclass;

    IF dep_cnt > 0 THEN
      new_name := 'hsa_legacy_' || to_char(now(), 'YYYYMMDD_HH24MISS');
      EXECUTE format('ALTER TABLE public.hsa RENAME TO %I;', new_name);
      RAISE NOTICE 'public.hsa had % FK dependencies; renamed to %', dep_cnt, new_name;
    ELSE
      EXECUTE 'DROP TABLE public.hsa;';
      RAISE NOTICE 'Dropped public.hsa (no FK dependencies).';
    END IF;
  END IF;
END $$;

-- -------------------------------------------------------------------
-- 2) CUSTODIAN: RENAME org_type TO custodian_kind + ADD CONSTRAINT
-- -------------------------------------------------------------------
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'c_custodian_org_type') THEN
    ALTER TABLE public.custodian DROP CONSTRAINT c_custodian_org_type;
  END IF;
END $$;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns 
             WHERE table_name = 'custodian' AND column_name = 'org_type') THEN
    ALTER TABLE public.custodian RENAME COLUMN org_type TO custodian_kind;
  END IF;
END $$;

ALTER TABLE public.custodian
  ADD COLUMN IF NOT EXISTS custodian_kind varchar(15);

ALTER TABLE public.custodian 
  ALTER COLUMN custodian_kind SET DEFAULT 'ODPEM';

UPDATE public.custodian
SET custodian_kind = CASE
  WHEN custodian_name ILIKE '%ODPEM%' THEN 'ODPEM'
  ELSE 'PARTNER'
END
WHERE custodian_kind IS NULL 
   OR custodian_kind NOT IN ('ODPEM','PARTNER');

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'custodian_kind_check'
  ) THEN
    ALTER TABLE public.custodian
      ADD CONSTRAINT custodian_kind_check
      CHECK (custodian_kind IS NULL OR custodian_kind IN ('ODPEM','PARTNER'));
  END IF;
END $$;

-- -------------------------------------------------------------------
-- 3) WAREHOUSE: RENAME COLUMNS + ADD allow_lastmile_issue
-- -------------------------------------------------------------------
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns 
             WHERE table_name = 'warehouse' AND column_name = 'warehouse_tier') THEN
    ALTER TABLE public.warehouse RENAME COLUMN warehouse_tier TO tier_code;
  END IF;
  
  IF EXISTS (SELECT 1 FROM information_schema.columns 
             WHERE table_name = 'warehouse' AND column_name = 'allows_donation_intake') THEN
    ALTER TABLE public.warehouse RENAME COLUMN allows_donation_intake TO allow_donation_intake;
  END IF;
END $$;

ALTER TABLE public.warehouse
  ADD COLUMN IF NOT EXISTS tier_code varchar(4),
  ADD COLUMN IF NOT EXISTS allow_donation_intake boolean NOT NULL DEFAULT true,
  ADD COLUMN IF NOT EXISTS allow_lastmile_issue boolean NOT NULL DEFAULT false;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'warehouse_tier_code_check'
  ) THEN
    ALTER TABLE public.warehouse
      ADD CONSTRAINT warehouse_tier_code_check
      CHECK (tier_code IS NULL OR tier_code IN ('MAIN','LSA','HSA'));
  END IF;
END $$;

-- Backfill tier_code for any NULL values
DO $$
DECLARE
  odpem_id int;
BEGIN
  SELECT custodian_id INTO odpem_id
  FROM public.custodian
  WHERE custodian_name ILIKE '%ODPEM%'
  ORDER BY custodian_id
  LIMIT 1;

  UPDATE public.warehouse w
  SET tier_code = CASE
    WHEN w.warehouse_type = 'MAIN-HUB' THEN 'MAIN'
    WHEN w.warehouse_type = 'SUB-HUB' AND odpem_id IS NOT NULL AND w.custodian_id = odpem_id THEN 'LSA'
    WHEN w.warehouse_type = 'SUB-HUB' AND odpem_id IS NOT NULL AND w.custodian_id <> odpem_id THEN 'HSA'
    ELSE w.tier_code
  END
  WHERE w.tier_code IS NULL;

  IF odpem_id IS NOT NULL THEN
    UPDATE public.warehouse
    SET allow_donation_intake = true
    WHERE tier_code = 'MAIN' AND custodian_id = odpem_id;

    UPDATE public.warehouse
    SET allow_donation_intake = false
    WHERE tier_code = 'LSA' AND custodian_id = odpem_id;

    UPDATE public.warehouse
    SET allow_donation_intake = true,
        allow_lastmile_issue  = true
    WHERE tier_code = 'HSA' AND custodian_id <> odpem_id;
  END IF;
END $$;

-- Views for filtering
CREATE OR REPLACE VIEW public.v_warehouse_main AS
SELECT * FROM public.warehouse WHERE tier_code = 'MAIN';

CREATE OR REPLACE VIEW public.v_warehouse_lsa AS
SELECT * FROM public.warehouse WHERE tier_code = 'LSA';

CREATE OR REPLACE VIEW public.v_warehouse_hsa AS
SELECT * FROM public.warehouse WHERE tier_code = 'HSA';

-- -------------------------------------------------------------------
-- 4) BENEFICIARY CONSTRAINTS (table already exists from prior migration)
-- -------------------------------------------------------------------
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'beneficiary_type_check') THEN
    ALTER TABLE public.beneficiary ADD CONSTRAINT beneficiary_type_check 
      CHECK (beneficiary_type IN ('INDIVIDUAL','SHELTER'));
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'beneficiary_status_check') THEN
    ALTER TABLE public.beneficiary ADD CONSTRAINT beneficiary_status_check 
      CHECK (status_code IN ('A','I'));
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_beneficiary_type ON public.beneficiary(beneficiary_type);
CREATE INDEX IF NOT EXISTS idx_beneficiary_parish ON public.beneficiary(parish_code);

-- -------------------------------------------------------------------
-- 5) TRANSACTION TABLE: ADD OPTIONAL BENEFICIARY/SOURCE REFERENCES
-- -------------------------------------------------------------------
ALTER TABLE public.transaction
  ADD COLUMN IF NOT EXISTS beneficiary_id integer,
  ADD COLUMN IF NOT EXISTS source_module varchar(30),
  ADD COLUMN IF NOT EXISTS source_record_id integer;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_transaction_beneficiary') THEN
    ALTER TABLE public.transaction
      ADD CONSTRAINT fk_transaction_beneficiary
      FOREIGN KEY (beneficiary_id) REFERENCES public.beneficiary(beneficiary_id);
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_transaction_beneficiary_id ON public.transaction(beneficiary_id);
CREATE INDEX IF NOT EXISTS idx_transaction_source_ref ON public.transaction(source_module, source_record_id);

COMMIT;
