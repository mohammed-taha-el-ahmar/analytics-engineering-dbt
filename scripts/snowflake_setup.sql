-- One-time setup for a Snowflake free-trial account.
-- Run this as ACCOUNTADMIN (or a role with CREATE WAREHOUSE/DATABASE/ROLE/USER
-- privileges) in a Snowflake worksheet, once.
--
-- Creates:
--   - An X-SMALL warehouse dedicated to dbt (auto-suspends after 60s idle,
--     so the free-trial credits aren't burned while you're not running dbt)
--   - A TRANSFORM_ROLE used by dbt
--   - An ANALYTICS database with RAW / STAGING / MARTS / MARTS_FINANCE
--     schemas, matching the +schema configs in dbt_project.yml
--   - A dbt service user (replace the password before running)

-- 1. Warehouse -----------------------------------------------------------
create warehouse if not exists transform_wh
  warehouse_size = 'XSMALL'
  auto_suspend = 60
  auto_resume = true
  initially_suspended = true
  comment = 'Warehouse used by dbt for this project';

-- 2. Role ------------------------------------------------------------------
create role if not exists transform_role;

grant usage on warehouse transform_wh to role transform_role;

-- 3. Database + schemas -----------------------------------------------------
create database if not exists analytics;

create schema if not exists analytics.raw;            -- loaded via dbt seed
create schema if not exists analytics.staging;         -- stg_ models (views)
create schema if not exists analytics.marts;           -- core marts (tables)
create schema if not exists analytics.marts_finance;   -- finance marts (incremental)

grant usage on database analytics to role transform_role;
grant all on schema analytics.raw            to role transform_role;
grant all on schema analytics.staging         to role transform_role;
grant all on schema analytics.marts           to role transform_role;
grant all on schema analytics.marts_finance   to role transform_role;

-- Future tables/views created by dbt in these schemas inherit the same grants
grant all on future tables in database analytics to role transform_role;
grant all on future views  in database analytics to role transform_role;

-- 4. Service user used by dbt -----------------------------------------------
-- Replace 'CHANGE_ME' with a strong password (or switch to key-pair auth —
-- see https://docs.getdbt.com/reference/warehouse-setups/snowflake-setup).
create user if not exists dbt_user
  password = 'CHANGE_ME'
  default_role = transform_role
  default_warehouse = transform_wh
  default_namespace = 'ANALYTICS.RAW'
  comment = 'Service account used by dbt (see profiles.yml.example)';

grant role transform_role to user dbt_user;

-- 5. Give your own user the role too, for browsing in Snowsight ------------
-- grant role transform_role to user <your_snowflake_username>;
