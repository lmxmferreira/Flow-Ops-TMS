-- ============================================================
-- Flow Ops TMS — Migration 001: Full Schema
-- Adapted from: enterprise_tms_functional_requirements.docx
-- Target schema: tms  |  Database: flow_ops_tms
--
-- Deploy command:
--   PGPASSWORD=oms_dev_password psql -h localhost -p 5433 -U oms_user -d flow_ops_tms -f migration_001_init.sql
--
-- Scope: configuration/lookup, org/party/user/master data,
--   PO management, order releases, loads, shipments, stops,
--   carrier tendering, rating, charges, cost allocation,
--   carrier invoice, freight audit, payable vouchers, payments,
--   client billing, accruals, accounting, financial reconciliation,
--   exceptions, claims, appointments, yard/dock/gate,
--   documents, integrations, workflows, reporting, traceability,
--   OMS event log (Flow Ops addition), numbering sequences.
-- ============================================================
BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE SCHEMA IF NOT EXISTS tms;
SET search_path = tms;

-- ---------------------------------------------------------------------------
-- Shared functions
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION touch_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

-- ---------------------------------------------------------------------------
-- Configuration and reference data
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS source_documents (
    source_document_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_name text NOT NULL,
    document_type text,
    source_path text,
    extracted_at timestamptz NOT NULL DEFAULT now(),
    notes text
);

CREATE TABLE IF NOT EXISTS functional_requirements (
    requirement_code text PRIMARY KEY,
    source_document_id uuid REFERENCES source_documents(source_document_id),
    module_name text NOT NULL,
    priority text NOT NULL,
    requirement_text text NOT NULL,
    status text NOT NULL DEFAULT 'active',
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS lookup_types (
    lookup_type_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    lookup_type_code text NOT NULL UNIQUE,
    lookup_type_name text NOT NULL,
    description text,
    status text NOT NULL DEFAULT 'active',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS lookup_values (
    lookup_value_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    lookup_type_id uuid NOT NULL REFERENCES lookup_types(lookup_type_id),
    lookup_code text NOT NULL,
    display_name text NOT NULL,
    description text,
    sort_order integer,
    parent_lookup_value_id uuid REFERENCES lookup_values(lookup_value_id),
    effective_start_date date,
    effective_end_date date,
    status text NOT NULL DEFAULT 'active',
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (lookup_type_id, lookup_code)
);

CREATE TABLE IF NOT EXISTS status_models (
    status_model_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    model_code text NOT NULL UNIQUE,
    model_name text NOT NULL,
    applies_to_entity text NOT NULL,
    description text,
    status text NOT NULL DEFAULT 'active',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS status_values (
    status_value_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    status_model_id uuid NOT NULL REFERENCES status_models(status_model_id) ON DELETE CASCADE,
    status_code text NOT NULL,
    status_name text NOT NULL,
    sort_order integer,
    is_initial boolean NOT NULL DEFAULT false,
    is_terminal boolean NOT NULL DEFAULT false,
    status text NOT NULL DEFAULT 'active',
    UNIQUE (status_model_id, status_code)
);

CREATE TABLE IF NOT EXISTS numbering_schemes (
    numbering_scheme_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    scheme_code text NOT NULL UNIQUE,
    applies_to_entity text NOT NULL,
    prefix text,
    suffix text,
    next_number bigint NOT NULL DEFAULT 1,
    padding_length integer NOT NULL DEFAULT 6,
    reset_frequency text,
    status text NOT NULL DEFAULT 'active',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS business_rules (
    business_rule_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_code text NOT NULL UNIQUE,
    rule_name text NOT NULL,
    applies_to_entity text NOT NULL,
    rule_type text NOT NULL,
    condition_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    action_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    effective_start_date date,
    effective_end_date date,
    status text NOT NULL DEFAULT 'active',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS validation_rules (
    validation_rule_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_code text NOT NULL UNIQUE,
    applies_to_entity text NOT NULL,
    field_name text,
    severity text NOT NULL DEFAULT 'error',
    validation_expression text,
    error_message text,
    status text NOT NULL DEFAULT 'active',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Enterprise, party, user, and master data
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS organizations (
    organization_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_code text NOT NULL UNIQUE,
    organization_name text NOT NULL,
    organization_type_id uuid REFERENCES lookup_values(lookup_value_id),
    parent_organization_id uuid REFERENCES organizations(organization_id),
    default_currency_id uuid REFERENCES lookup_values(lookup_value_id),
    country_id uuid REFERENCES lookup_values(lookup_value_id),
    status_id uuid REFERENCES lookup_values(lookup_value_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS business_units (
    business_unit_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(organization_id),
    business_unit_code text NOT NULL,
    business_unit_name text NOT NULL,
    parent_business_unit_id uuid REFERENCES business_units(business_unit_id),
    status_id uuid REFERENCES lookup_values(lookup_value_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, business_unit_code)
);

CREATE TABLE IF NOT EXISTS parties (
    party_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    party_code text NOT NULL UNIQUE,
    party_name text NOT NULL,
    party_type_id uuid REFERENCES lookup_values(lookup_value_id),
    parent_party_id uuid REFERENCES parties(party_id),
    tax_identifier text,
    default_currency_id uuid REFERENCES lookup_values(lookup_value_id),
    payment_terms_id uuid REFERENCES lookup_values(lookup_value_id),
    status_id uuid REFERENCES lookup_values(lookup_value_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS party_roles (
    party_role_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    party_id uuid NOT NULL REFERENCES parties(party_id) ON DELETE CASCADE,
    role_type_id uuid NOT NULL REFERENCES lookup_values(lookup_value_id),
    business_unit_id uuid REFERENCES business_units(business_unit_id),
    status_id uuid REFERENCES lookup_values(lookup_value_id),
    UNIQUE (party_id, role_type_id, business_unit_id)
);

CREATE TABLE IF NOT EXISTS contacts (
    contact_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    party_id uuid REFERENCES parties(party_id),
    contact_name text NOT NULL,
    contact_role text,
    email text,
    phone text,
    mobile_phone text,
    status_id uuid REFERENCES lookup_values(lookup_value_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS locations (
    location_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    location_code text NOT NULL UNIQUE,
    location_name text NOT NULL,
    party_id uuid REFERENCES parties(party_id),
    location_type_id uuid REFERENCES lookup_values(lookup_value_id),
    address_line1 text,
    address_line2 text,
    city text,
    state_province text,
    postal_code text,
    country_id uuid REFERENCES lookup_values(lookup_value_id),
    latitude numeric(11, 8),
    longitude numeric(11, 8),
    time_zone text,
    status_id uuid REFERENCES lookup_values(lookup_value_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS external_systems (
    external_system_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    system_code text NOT NULL UNIQUE,
    system_name text NOT NULL,
    system_type_id uuid REFERENCES lookup_values(lookup_value_id),
    owning_party_id uuid REFERENCES parties(party_id),
    base_endpoint text,
    status_id uuid REFERENCES lookup_values(lookup_value_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS external_references (
    external_reference_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    external_system_id uuid NOT NULL REFERENCES external_systems(external_system_id),
    entity_type text NOT NULL,
    entity_id uuid NOT NULL,
    external_reference_type text NOT NULL,
    external_reference_value text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (external_system_id, entity_type, external_reference_type, external_reference_value)
);

CREATE TABLE IF NOT EXISTS app_users (
    user_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    party_id uuid REFERENCES parties(party_id),
    business_unit_id uuid REFERENCES business_units(business_unit_id),
    user_name text NOT NULL UNIQUE,
    display_name text NOT NULL,
    email text NOT NULL UNIQUE,
    language_code text,
    time_zone text,
    status_id uuid REFERENCES lookup_values(lookup_value_id),
    last_login_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS roles (
    role_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    role_code text NOT NULL UNIQUE,
    role_name text NOT NULL,
    role_type_id uuid REFERENCES lookup_values(lookup_value_id),
    status_id uuid REFERENCES lookup_values(lookup_value_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS permissions (
    permission_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    permission_code text NOT NULL UNIQUE,
    permission_name text NOT NULL,
    permission_scope text NOT NULL,
    description text
);

CREATE TABLE IF NOT EXISTS role_permissions (
    role_id uuid NOT NULL REFERENCES roles(role_id) ON DELETE CASCADE,
    permission_id uuid NOT NULL REFERENCES permissions(permission_id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE IF NOT EXISTS user_roles (
    user_id uuid NOT NULL REFERENCES app_users(user_id) ON DELETE CASCADE,
    role_id uuid NOT NULL REFERENCES roles(role_id) ON DELETE CASCADE,
    business_unit_id uuid REFERENCES business_units(business_unit_id),
    effective_start_date date,
    effective_end_date date,
    PRIMARY KEY (user_id, role_id, business_unit_id)
);

CREATE TABLE IF NOT EXISTS unit_of_measures (
    uom_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    uom_code text NOT NULL UNIQUE,
    uom_name text NOT NULL,
    uom_category_id uuid REFERENCES lookup_values(lookup_value_id),
    status_id uuid REFERENCES lookup_values(lookup_value_id)
);

CREATE TABLE IF NOT EXISTS uom_conversions (
    uom_conversion_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    from_uom_id uuid NOT NULL REFERENCES unit_of_measures(uom_id),
    to_uom_id uuid NOT NULL REFERENCES unit_of_measures(uom_id),
    conversion_factor numeric(24, 12) NOT NULL CHECK (conversion_factor > 0),
    effective_start_date date,
    effective_end_date date,
    UNIQUE (from_uom_id, to_uom_id, effective_start_date)
);

CREATE TABLE IF NOT EXISTS commodities (
    commodity_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    commodity_code text NOT NULL UNIQUE,
    commodity_name text NOT NULL,
    freight_class_id uuid REFERENCES lookup_values(lookup_value_id),
    nmfc_code text,
    hazmat_class_id uuid REFERENCES lookup_values(lookup_value_id),
    status_id uuid REFERENCES lookup_values(lookup_value_id)
);

CREATE TABLE IF NOT EXISTS items (
    item_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    item_number text NOT NULL UNIQUE,
    item_description text NOT NULL,
    commodity_id uuid REFERENCES commodities(commodity_id),
    default_uom_id uuid REFERENCES unit_of_measures(uom_id),
    weight_value numeric(18, 6),
    weight_uom_id uuid REFERENCES unit_of_measures(uom_id),
    length_value numeric(18, 6),
    width_value numeric(18, 6),
    height_value numeric(18, 6),
    dimension_uom_id uuid REFERENCES unit_of_measures(uom_id),
    cube_value numeric(18, 6),
    cube_uom_id uuid REFERENCES unit_of_measures(uom_id),
    hazardous_flag boolean NOT NULL DEFAULT false,
    temperature_requirement text,
    packaging_type_id uuid REFERENCES lookup_values(lookup_value_id),
    stackable_flag boolean,
    status_id uuid REFERENCES lookup_values(lookup_value_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS item_aliases (
    item_alias_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    item_id uuid NOT NULL REFERENCES items(item_id) ON DELETE CASCADE,
    party_id uuid REFERENCES parties(party_id),
    external_system_id uuid REFERENCES external_systems(external_system_id),
    alias_type text NOT NULL,
    alias_value text NOT NULL,
    status_id uuid REFERENCES lookup_values(lookup_value_id),
    UNIQUE (item_id, party_id, external_system_id, alias_type, alias_value)
);

CREATE TABLE IF NOT EXISTS equipment_types (
    equipment_type_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    equipment_code text NOT NULL UNIQUE,
    equipment_name text NOT NULL,
    equipment_category_id uuid REFERENCES lookup_values(lookup_value_id),
    max_weight numeric(18, 6),
    max_volume numeric(18, 6),
    length_value numeric(18, 6),
    width_value numeric(18, 6),
    height_value numeric(18, 6),
    temperature_controlled_flag boolean NOT NULL DEFAULT false,
    status_id uuid REFERENCES lookup_values(lookup_value_id)
);

CREATE TABLE IF NOT EXISTS transport_modes (
    transport_mode_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    mode_code text NOT NULL UNIQUE,
    mode_name text NOT NULL,
    mode_type_id uuid REFERENCES lookup_values(lookup_value_id),
    status_id uuid REFERENCES lookup_values(lookup_value_id)
);

CREATE TABLE IF NOT EXISTS service_levels (
    service_level_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    service_level_code text NOT NULL UNIQUE,
    service_level_name text NOT NULL,
    transit_time_hours numeric(18, 3),
    priority_rank integer,
    status_id uuid REFERENCES lookup_values(lookup_value_id)
);

CREATE TABLE IF NOT EXISTS lanes (
    lane_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    lane_code text NOT NULL UNIQUE,
    origin_location_id uuid REFERENCES locations(location_id),
    destination_location_id uuid REFERENCES locations(location_id),
    origin_zone_id uuid REFERENCES lookup_values(lookup_value_id),
    destination_zone_id uuid REFERENCES lookup_values(lookup_value_id),
    transport_mode_id uuid REFERENCES transport_modes(transport_mode_id),
    distance_value numeric(18, 3),
    distance_uom_id uuid REFERENCES unit_of_measures(uom_id),
    status_id uuid REFERENCES lookup_values(lookup_value_id)
);

CREATE TABLE IF NOT EXISTS gl_accounts (
    gl_account_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    account_code text NOT NULL UNIQUE,
    account_name text NOT NULL,
    account_type_id uuid REFERENCES lookup_values(lookup_value_id),
    status_id uuid REFERENCES lookup_values(lookup_value_id)
);

CREATE TABLE IF NOT EXISTS cost_centers (
    cost_center_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    cost_center_code text NOT NULL UNIQUE,
    cost_center_name text NOT NULL,
    business_unit_id uuid REFERENCES business_units(business_unit_id),
    status_id uuid REFERENCES lookup_values(lookup_value_id)
);

CREATE TABLE IF NOT EXISTS projects (
    project_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_code text NOT NULL UNIQUE,
    project_name text NOT NULL,
    customer_party_id uuid REFERENCES parties(party_id),
    cost_center_id uuid REFERENCES cost_centers(cost_center_id),
    status_id uuid REFERENCES lookup_values(lookup_value_id)
);

CREATE TABLE IF NOT EXISTS charge_codes (
    charge_code_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    charge_code text NOT NULL UNIQUE,
    charge_name text NOT NULL,
    charge_category_id uuid REFERENCES lookup_values(lookup_value_id),
    default_gl_account_id uuid REFERENCES gl_accounts(gl_account_id),
    taxable_flag boolean NOT NULL DEFAULT false,
    billable_flag boolean NOT NULL DEFAULT true,
    payable_flag boolean NOT NULL DEFAULT true,
    status_id uuid REFERENCES lookup_values(lookup_value_id)
);

CREATE TABLE IF NOT EXISTS carriers (
    carrier_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    party_id uuid NOT NULL UNIQUE REFERENCES parties(party_id),
    scac text,
    mc_number text,
    dot_number text,
    safety_rating_id uuid REFERENCES lookup_values(lookup_value_id),
    remittance_party_id uuid REFERENCES parties(party_id),
    payment_terms_id uuid REFERENCES lookup_values(lookup_value_id),
    status_id uuid REFERENCES lookup_values(lookup_value_id),
    onboarding_status_id uuid REFERENCES lookup_values(lookup_value_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS carrier_services (
    carrier_service_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    carrier_id uuid NOT NULL REFERENCES carriers(carrier_id),
    transport_mode_id uuid REFERENCES transport_modes(transport_mode_id),
    service_level_id uuid REFERENCES service_levels(service_level_id),
    equipment_type_id uuid REFERENCES equipment_types(equipment_type_id),
    lane_id uuid REFERENCES lanes(lane_id),
    status_id uuid REFERENCES lookup_values(lookup_value_id),
    UNIQUE (carrier_id, transport_mode_id, service_level_id, equipment_type_id, lane_id)
);

CREATE TABLE IF NOT EXISTS carrier_compliance_records (
    compliance_record_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    carrier_id uuid NOT NULL REFERENCES carriers(carrier_id),
    compliance_type_id uuid REFERENCES lookup_values(lookup_value_id),
    document_id uuid,
    certificate_number text,
    effective_date date,
    expiration_date date,
    status_id uuid REFERENCES lookup_values(lookup_value_id),
    notes text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS carrier_scorecards (
    carrier_scorecard_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    carrier_id uuid NOT NULL REFERENCES carriers(carrier_id),
    period_start_date date NOT NULL,
    period_end_date date NOT NULL,
    tender_acceptance_pct numeric(8, 4),
    avg_response_minutes numeric(18, 3),
    on_time_pickup_pct numeric(8, 4),
    on_time_delivery_pct numeric(8, 4),
    tracking_compliance_pct numeric(8, 4),
    invoice_accuracy_pct numeric(8, 4),
    claims_count integer NOT NULL DEFAULT 0,
    service_failures_count integer NOT NULL DEFAULT 0,
    total_score numeric(8, 4),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (carrier_id, period_start_date, period_end_date)
);

-- ---------------------------------------------------------------------------
-- Purchase order and PO line management
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS purchase_orders (
    purchase_order_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    purchase_order_number text NOT NULL,
    purchase_order_type_id uuid REFERENCES lookup_values(lookup_value_id),
    buyer_party_id uuid REFERENCES parties(party_id),
    supplier_party_id uuid NOT NULL REFERENCES parties(party_id),
    ship_from_location_id uuid REFERENCES locations(location_id),
    ship_to_location_id uuid REFERENCES locations(location_id),
    incoterm_id uuid REFERENCES lookup_values(lookup_value_id),
    freight_terms_id uuid REFERENCES lookup_values(lookup_value_id),
    currency_id uuid REFERENCES lookup_values(lookup_value_id),
    payment_terms_id uuid REFERENCES lookup_values(lookup_value_id),
    requested_ship_date date,
    requested_delivery_date date,
    priority_id uuid REFERENCES lookup_values(lookup_value_id),
    owning_business_unit_id uuid REFERENCES business_units(business_unit_id),
    project_id uuid REFERENCES projects(project_id),
    cost_center_id uuid REFERENCES cost_centers(cost_center_id),
    source_system_id uuid REFERENCES external_systems(external_system_id),
    source_reference text,
    status_id uuid REFERENCES lookup_values(lookup_value_id),
    hold_flag boolean NOT NULL DEFAULT false,
    hold_reason_id uuid REFERENCES lookup_values(lookup_value_id),
    version_number integer NOT NULL DEFAULT 1,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (supplier_party_id, purchase_order_number, source_system_id)
);

CREATE TABLE IF NOT EXISTS purchase_order_lines (
    purchase_order_line_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    purchase_order_id uuid NOT NULL REFERENCES purchase_orders(purchase_order_id) ON DELETE CASCADE,
    line_number text NOT NULL,
    item_id uuid REFERENCES items(item_id),
    item_description text,
    ordered_quantity numeric(18, 6) NOT NULL DEFAULT 0,
    releasable_quantity numeric(18, 6) NOT NULL DEFAULT 0,
    released_quantity numeric(18, 6) NOT NULL DEFAULT 0,
    planned_quantity numeric(18, 6) NOT NULL DEFAULT 0,
    shipped_quantity numeric(18, 6) NOT NULL DEFAULT 0,
    delivered_quantity numeric(18, 6) NOT NULL DEFAULT 0,
    received_quantity numeric(18, 6) NOT NULL DEFAULT 0,
    canceled_quantity numeric(18, 6) NOT NULL DEFAULT 0,
    remaining_quantity numeric(18, 6) NOT NULL DEFAULT 0,
    quantity_uom_id uuid REFERENCES unit_of_measures(uom_id),
    weight_value numeric(18, 6),
    weight_uom_id uuid REFERENCES unit_of_measures(uom_id),
    volume_value numeric(18, 6),
    volume_uom_id uuid REFERENCES unit_of_measures(uom_id),
    freight_class_id uuid REFERENCES lookup_values(lookup_value_id),
    hazardous_flag boolean NOT NULL DEFAULT false,
    temperature_requirement text,
    packaging_type_id uuid REFERENCES lookup_values(lookup_value_id),
    requested_ship_date date,
    requested_delivery_date date,
    line_value numeric(18, 2),
    currency_id uuid REFERENCES lookup_values(lookup_value_id),
    status_id uuid REFERENCES lookup_values(lookup_value_id),
    hold_flag boolean NOT NULL DEFAULT false,
    hold_reason_id uuid REFERENCES lookup_values(lookup_value_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (ordered_quantity >= 0),
    CHECK (released_quantity >= 0),
    UNIQUE (purchase_order_id, line_number)
);

CREATE TABLE IF NOT EXISTS purchase_order_versions (
    purchase_order_version_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    purchase_order_id uuid NOT NULL REFERENCES purchase_orders(purchase_order_id) ON DELETE CASCADE,
    version_number integer NOT NULL,
    change_reason_id uuid REFERENCES lookup_values(lookup_value_id),
    snapshot_json jsonb NOT NULL,
    created_by_user_id uuid REFERENCES app_users(user_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (purchase_order_id, version_number)
);

-- ---------------------------------------------------------------------------
-- Release and order release management
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS release_rules (
    release_rule_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    release_rule_code text NOT NULL UNIQUE,
    release_rule_name text NOT NULL,
    supplier_party_id uuid REFERENCES parties(party_id),
    customer_party_id uuid REFERENCES parties(party_id),
    business_unit_id uuid REFERENCES business_units(business_unit_id),
    condition_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    action_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    status_id uuid REFERENCES lookup_values(lookup_value_id),
    effective_start_date date,
    effective_end_date date,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS order_releases (
    order_release_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    order_release_number text NOT NULL UNIQUE,
    release_source_type_id uuid REFERENCES lookup_values(lookup_value_id),
    source_purchase_order_id uuid REFERENCES purchase_orders(purchase_order_id),
    customer_party_id uuid REFERENCES parties(party_id),
    supplier_party_id uuid REFERENCES parties(party_id),
    shipper_location_id uuid REFERENCES locations(location_id),
    consignee_location_id uuid REFERENCES locations(location_id),
    requested_ship_date date,
    requested_delivery_date date,
    transport_mode_id uuid REFERENCES transport_modes(transport_mode_id),
    service_level_id uuid REFERENCES service_levels(service_level_id),
    equipment_type_id uuid REFERENCES equipment_types(equipment_type_id),
    freight_terms_id uuid REFERENCES lookup_values(lookup_value_id),
    priority_id uuid REFERENCES lookup_values(lookup_value_id),
    responsible_party_id uuid REFERENCES parties(party_id),
    status_id uuid REFERENCES lookup_values(lookup_value_id),
    release_rule_id uuid REFERENCES release_rules(release_rule_id),
    override_reason_id uuid REFERENCES lookup_values(lookup_value_id),
    created_by_user_id uuid REFERENCES app_users(user_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS order_release_lines (
    order_release_line_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    order_release_id uuid NOT NULL REFERENCES order_releases(order_release_id) ON DELETE CASCADE,
    line_number text NOT NULL,
    purchase_order_line_id uuid REFERENCES purchase_order_lines(purchase_order_line_id),
    item_id uuid REFERENCES items(item_id),
    quantity numeric(18, 6) NOT NULL DEFAULT 0,
    quantity_uom_id uuid REFERENCES unit_of_measures(uom_id),
    weight_value numeric(18, 6),
    weight_uom_id uuid REFERENCES unit_of_measures(uom_id),
    cube_value numeric(18, 6),
    cube_uom_id uuid REFERENCES unit_of_measures(uom_id),
    line_value numeric(18, 2),
    currency_id uuid REFERENCES lookup_values(lookup_value_id),
    hazardous_flag boolean NOT NULL DEFAULT false,
    temperature_requirement text,
    packaging_type_id uuid REFERENCES lookup_values(lookup_value_id),
    handling_instructions text,
    status_id uuid REFERENCES lookup_values(lookup_value_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (quantity >= 0),
    UNIQUE (order_release_id, line_number)
);

CREATE TABLE IF NOT EXISTS release_events (
    release_event_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    order_release_id uuid REFERENCES order_releases(order_release_id),
    order_release_line_id uuid REFERENCES order_release_lines(order_release_line_id),
    event_type_id uuid REFERENCES lookup_values(lookup_value_id),
    event_timestamp timestamptz NOT NULL DEFAULT now(),
    quantity numeric(18, 6),
    source_channel_id uuid REFERENCES lookup_values(lookup_value_id),
    created_by_user_id uuid REFERENCES app_users(user_id),
    notes text,
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb
);

-- ---------------------------------------------------------------------------
-- Shipment, load, stop, and execution management
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS loads (
    load_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    load_number text NOT NULL UNIQUE,
    load_type_id uuid REFERENCES lookup_values(lookup_value_id),
    carrier_id uuid REFERENCES carriers(carrier_id),
    transport_mode_id uuid REFERENCES transport_modes(transport_mode_id),
    service_level_id uuid REFERENCES service_levels(service_level_id),
    equipment_type_id uuid REFERENCES equipment_types(equipment_type_id),
    planned_start_datetime timestamptz,
    planned_end_datetime timestamptz,
    actual_start_datetime timestamptz,
    actual_end_datetime timestamptz,
    status_id uuid REFERENCES lookup_values(lookup_value_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS shipments (
    shipment_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    shipment_number text NOT NULL UNIQUE,
    shipment_type_id uuid REFERENCES lookup_values(lookup_value_id),
    shipment_status_id uuid REFERENCES lookup_values(lookup_value_id),
    customer_party_id uuid REFERENCES parties(party_id),
    supplier_party_id uuid REFERENCES parties(party_id),
    carrier_id uuid REFERENCES carriers(carrier_id),
    transport_mode_id uuid REFERENCES transport_modes(transport_mode_id),
    service_level_id uuid REFERENCES service_levels(service_level_id),
    equipment_type_id uuid REFERENCES equipment_types(equipment_type_id),
    origin_location_id uuid REFERENCES locations(location_id),
    destination_location_id uuid REFERENCES locations(location_id),
    planned_pickup_datetime timestamptz,
    planned_delivery_datetime timestamptz,
    actual_pickup_datetime timestamptz,
    actual_delivery_datetime timestamptz,
    freight_terms_id uuid REFERENCES lookup_values(lookup_value_id),
    financial_owner_party_id uuid REFERENCES parties(party_id),
    total_weight numeric(18, 6),
    total_volume numeric(18, 6),
    pallet_count numeric(18, 6),
    carton_count numeric(18, 6),
    unit_count numeric(18, 6),
    linear_feet numeric(18, 6),
    distance_value numeric(18, 3),
    distance_uom_id uuid REFERENCES unit_of_measures(uom_id),
    chargeable_weight numeric(18, 6),
    currency_id uuid REFERENCES lookup_values(lookup_value_id),
    closeout_completed_flag boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS load_shipments (
    load_id uuid NOT NULL REFERENCES loads(load_id) ON DELETE CASCADE,
    shipment_id uuid NOT NULL REFERENCES shipments(shipment_id) ON DELETE CASCADE,
    sequence_number integer,
    PRIMARY KEY (load_id, shipment_id)
);

CREATE TABLE IF NOT EXISTS shipment_order_releases (
    shipment_id uuid NOT NULL REFERENCES shipments(shipment_id) ON DELETE CASCADE,
    order_release_id uuid NOT NULL REFERENCES order_releases(order_release_id) ON DELETE CASCADE,
    PRIMARY KEY (shipment_id, order_release_id)
);

CREATE TABLE IF NOT EXISTS shipment_lines (
    shipment_line_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    shipment_id uuid NOT NULL REFERENCES shipments(shipment_id) ON DELETE CASCADE,
    order_release_line_id uuid REFERENCES order_release_lines(order_release_line_id),
    purchase_order_line_id uuid REFERENCES purchase_order_lines(purchase_order_line_id),
    item_id uuid REFERENCES items(item_id),
    planned_quantity numeric(18, 6) NOT NULL DEFAULT 0,
    actual_quantity numeric(18, 6) NOT NULL DEFAULT 0,
    quantity_uom_id uuid REFERENCES unit_of_measures(uom_id),
    shipped_weight numeric(18, 6),
    delivered_quantity numeric(18, 6),
    damaged_quantity numeric(18, 6),
    shortage_quantity numeric(18, 6),
    overage_quantity numeric(18, 6),
    status_id uuid REFERENCES lookup_values(lookup_value_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS shipment_stops (
    shipment_stop_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    shipment_id uuid NOT NULL REFERENCES shipments(shipment_id) ON DELETE CASCADE,
    stop_sequence integer NOT NULL,
    stop_type_id uuid REFERENCES lookup_values(lookup_value_id),
    location_id uuid REFERENCES locations(location_id),
    appointment_datetime timestamptz,
    planned_arrival_datetime timestamptz,
    planned_departure_datetime timestamptz,
    actual_arrival_datetime timestamptz,
    actual_departure_datetime timestamptz,
    service_start_datetime timestamptz,
    service_end_datetime timestamptz,
    contact_id uuid REFERENCES contacts(contact_id),
    instructions text,
    stop_status_id uuid REFERENCES lookup_values(lookup_value_id),
    dwell_minutes numeric(18, 3),
    detention_minutes numeric(18, 3),
    late_minutes numeric(18, 3),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (shipment_id, stop_sequence)
);

CREATE TABLE IF NOT EXISTS stop_order_releases (
    shipment_stop_id uuid NOT NULL REFERENCES shipment_stops(shipment_stop_id) ON DELETE CASCADE,
    order_release_id uuid NOT NULL REFERENCES order_releases(order_release_id) ON DELETE CASCADE,
    pickup_quantity numeric(18, 6),
    delivery_quantity numeric(18, 6),
    quantity_uom_id uuid REFERENCES unit_of_measures(uom_id),
    PRIMARY KEY (shipment_stop_id, order_release_id)
);

CREATE TABLE IF NOT EXISTS stop_activity_templates (
    stop_activity_template_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    activity_code text NOT NULL UNIQUE,
    activity_name text NOT NULL,
    activity_type_id uuid REFERENCES lookup_values(lookup_value_id),
    required_behavior_id uuid REFERENCES lookup_values(lookup_value_id),
    condition_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    status_id uuid REFERENCES lookup_values(lookup_value_id)
);

CREATE TABLE IF NOT EXISTS stop_activities (
    stop_activity_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    shipment_stop_id uuid NOT NULL REFERENCES shipment_stops(shipment_stop_id) ON DELETE CASCADE,
    stop_activity_template_id uuid REFERENCES stop_activity_templates(stop_activity_template_id),
    activity_type_id uuid REFERENCES lookup_values(lookup_value_id),
    activity_status_id uuid REFERENCES lookup_values(lookup_value_id),
    required_flag boolean NOT NULL DEFAULT false,
    started_at timestamptz,
    completed_at timestamptz,
    completed_by_user_id uuid REFERENCES app_users(user_id),
    device_identifier text,
    evidence_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    override_reason_id uuid REFERENCES lookup_values(lookup_value_id),
    notes text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS shipment_assets (
    shipment_asset_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    shipment_id uuid REFERENCES shipments(shipment_id) ON DELETE CASCADE,
    load_id uuid REFERENCES loads(load_id) ON DELETE CASCADE,
    asset_type_id uuid REFERENCES lookup_values(lookup_value_id),
    asset_identifier text NOT NULL,
    assigned_at timestamptz NOT NULL DEFAULT now(),
    unassigned_at timestamptz,
    UNIQUE (shipment_id, load_id, asset_type_id, asset_identifier)
);

CREATE TABLE IF NOT EXISTS tracking_events (
    tracking_event_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    shipment_id uuid REFERENCES shipments(shipment_id) ON DELETE CASCADE,
    load_id uuid REFERENCES loads(load_id) ON DELETE CASCADE,
    shipment_stop_id uuid REFERENCES shipment_stops(shipment_stop_id),
    event_type_id uuid REFERENCES lookup_values(lookup_value_id),
    event_status_id uuid REFERENCES lookup_values(lookup_value_id),
    event_datetime timestamptz NOT NULL,
    event_source_id uuid REFERENCES lookup_values(lookup_value_id),
    latitude numeric(11, 8),
    longitude numeric(11, 8),
    city text,
    state_province text,
    country_id uuid REFERENCES lookup_values(lookup_value_id),
    eta_datetime timestamptz,
    correction_flag boolean NOT NULL DEFAULT false,
    corrected_tracking_event_id uuid REFERENCES tracking_events(tracking_event_id),
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS milestones (
    milestone_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    shipment_id uuid REFERENCES shipments(shipment_id) ON DELETE CASCADE,
    load_id uuid REFERENCES loads(load_id) ON DELETE CASCADE,
    milestone_type_id uuid REFERENCES lookup_values(lookup_value_id),
    planned_datetime timestamptz,
    actual_datetime timestamptz,
    milestone_status_id uuid REFERENCES lookup_values(lookup_value_id),
    source_tracking_event_id uuid REFERENCES tracking_events(tracking_event_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Carrier tendering and capacity
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS carrier_capacity_commitments (
    capacity_commitment_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    carrier_id uuid NOT NULL REFERENCES carriers(carrier_id),
    lane_id uuid REFERENCES lanes(lane_id),
    equipment_type_id uuid REFERENCES equipment_types(equipment_type_id),
    commitment_period_start date NOT NULL,
    commitment_period_end date NOT NULL,
    committed_capacity numeric(18, 6) NOT NULL,
    used_capacity numeric(18, 6) NOT NULL DEFAULT 0,
    capacity_uom_id uuid REFERENCES unit_of_measures(uom_id),
    status_id uuid REFERENCES lookup_values(lookup_value_id)
);

CREATE TABLE IF NOT EXISTS rate_contracts (
    rate_contract_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_number text NOT NULL UNIQUE,
    contract_type_id uuid REFERENCES lookup_values(lookup_value_id),
    carrier_id uuid REFERENCES carriers(carrier_id),
    customer_party_id uuid REFERENCES parties(party_id),
    business_unit_id uuid REFERENCES business_units(business_unit_id),
    currency_id uuid REFERENCES lookup_values(lookup_value_id),
    effective_start_date date NOT NULL,
    effective_end_date date,
    version_number integer NOT NULL DEFAULT 1,
    status_id uuid REFERENCES lookup_values(lookup_value_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tenders (
    tender_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tender_number text NOT NULL UNIQUE,
    shipment_id uuid REFERENCES shipments(shipment_id),
    load_id uuid REFERENCES loads(load_id),
    carrier_id uuid NOT NULL REFERENCES carriers(carrier_id),
    tender_method_id uuid REFERENCES lookup_values(lookup_value_id),
    tender_status_id uuid REFERENCES lookup_values(lookup_value_id),
    offered_amount numeric(18, 2),
    currency_id uuid REFERENCES lookup_values(lookup_value_id),
    rate_contract_id uuid REFERENCES rate_contracts(rate_contract_id),
    sent_at timestamptz,
    expires_at timestamptz,
    responded_at timestamptz,
    response_reason_id uuid REFERENCES lookup_values(lookup_value_id),
    counteroffer_amount numeric(18, 2),
    communication_channel_id uuid REFERENCES lookup_values(lookup_value_id),
    created_by_user_id uuid REFERENCES app_users(user_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tender_events (
    tender_event_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tender_id uuid NOT NULL REFERENCES tenders(tender_id) ON DELETE CASCADE,
    event_type_id uuid REFERENCES lookup_values(lookup_value_id),
    event_timestamp timestamptz NOT NULL DEFAULT now(),
    actor_party_id uuid REFERENCES parties(party_id),
    actor_user_id uuid REFERENCES app_users(user_id),
    notes text,
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb
);

-- ---------------------------------------------------------------------------
-- Rating, charges, allocation, and financial calculation
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS rate_rules (
    rate_rule_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    rate_contract_id uuid NOT NULL REFERENCES rate_contracts(rate_contract_id) ON DELETE CASCADE,
    rate_rule_code text NOT NULL,
    charge_code_id uuid NOT NULL REFERENCES charge_codes(charge_code_id),
    rate_basis_id uuid REFERENCES lookup_values(lookup_value_id),
    lane_id uuid REFERENCES lanes(lane_id),
    transport_mode_id uuid REFERENCES transport_modes(transport_mode_id),
    equipment_type_id uuid REFERENCES equipment_types(equipment_type_id),
    service_level_id uuid REFERENCES service_levels(service_level_id),
    min_charge_amount numeric(18, 2),
    max_charge_amount numeric(18, 2),
    rate_amount numeric(18, 6),
    formula_text text,
    condition_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    status_id uuid REFERENCES lookup_values(lookup_value_id),
    UNIQUE (rate_contract_id, rate_rule_code)
);

CREATE TABLE IF NOT EXISTS fuel_surcharge_schedules (
    fuel_surcharge_schedule_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    schedule_code text NOT NULL UNIQUE,
    carrier_id uuid REFERENCES carriers(carrier_id),
    rate_contract_id uuid REFERENCES rate_contracts(rate_contract_id),
    fuel_index_id uuid REFERENCES lookup_values(lookup_value_id),
    base_fuel_price numeric(18, 6),
    effective_start_date date,
    effective_end_date date,
    rules_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    status_id uuid REFERENCES lookup_values(lookup_value_id)
);

CREATE TABLE IF NOT EXISTS rating_results (
    rating_result_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    rating_run_number text NOT NULL UNIQUE,
    shipment_id uuid REFERENCES shipments(shipment_id),
    load_id uuid REFERENCES loads(load_id),
    order_release_id uuid REFERENCES order_releases(order_release_id),
    purchase_order_id uuid REFERENCES purchase_orders(purchase_order_id),
    rate_contract_id uuid REFERENCES rate_contracts(rate_contract_id),
    rate_type_id uuid REFERENCES lookup_values(lookup_value_id),
    rated_at timestamptz NOT NULL DEFAULT now(),
    rated_by_user_id uuid REFERENCES app_users(user_id),
    total_carrier_cost numeric(18, 2) NOT NULL DEFAULT 0,
    total_client_billable numeric(18, 2) NOT NULL DEFAULT 0,
    gross_margin_amount numeric(18, 2) NOT NULL DEFAULT 0,
    currency_id uuid REFERENCES lookup_values(lookup_value_id),
    rating_status_id uuid REFERENCES lookup_values(lookup_value_id),
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS charges (
    charge_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    charge_number text NOT NULL UNIQUE,
    charge_code_id uuid NOT NULL REFERENCES charge_codes(charge_code_id),
    charge_source_type text NOT NULL,
    charge_source_id uuid NOT NULL,
    shipment_id uuid REFERENCES shipments(shipment_id),
    load_id uuid REFERENCES loads(load_id),
    shipment_stop_id uuid REFERENCES shipment_stops(shipment_stop_id),
    order_release_id uuid REFERENCES order_releases(order_release_id),
    purchase_order_id uuid REFERENCES purchase_orders(purchase_order_id),
    purchase_order_line_id uuid REFERENCES purchase_order_lines(purchase_order_line_id),
    carrier_id uuid REFERENCES carriers(carrier_id),
    customer_party_id uuid REFERENCES parties(party_id),
    rating_result_id uuid REFERENCES rating_results(rating_result_id),
    quantity numeric(18, 6) DEFAULT 1,
    rate_amount numeric(18, 6),
    charge_amount numeric(18, 2) NOT NULL DEFAULT 0,
    tax_amount numeric(18, 2) NOT NULL DEFAULT 0,
    currency_id uuid REFERENCES lookup_values(lookup_value_id),
    payable_flag boolean NOT NULL DEFAULT true,
    billable_flag boolean NOT NULL DEFAULT true,
    approved_flag boolean NOT NULL DEFAULT false,
    charge_status_id uuid REFERENCES lookup_values(lookup_value_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS allocation_rules (
    allocation_rule_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    allocation_rule_code text NOT NULL UNIQUE,
    allocation_rule_name text NOT NULL,
    charge_code_id uuid REFERENCES charge_codes(charge_code_id),
    customer_party_id uuid REFERENCES parties(party_id),
    business_unit_id uuid REFERENCES business_units(business_unit_id),
    allocation_method_id uuid REFERENCES lookup_values(lookup_value_id),
    rounding_rule_id uuid REFERENCES lookup_values(lookup_value_id),
    condition_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    status_id uuid REFERENCES lookup_values(lookup_value_id),
    effective_start_date date,
    effective_end_date date
);

CREATE TABLE IF NOT EXISTS cost_allocations (
    cost_allocation_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    allocation_number text NOT NULL UNIQUE,
    charge_id uuid NOT NULL REFERENCES charges(charge_id),
    allocation_rule_id uuid REFERENCES allocation_rules(allocation_rule_id),
    allocation_status_id uuid REFERENCES lookup_values(lookup_value_id),
    total_allocated_amount numeric(18, 2) NOT NULL DEFAULT 0,
    currency_id uuid REFERENCES lookup_values(lookup_value_id),
    version_number integer NOT NULL DEFAULT 1,
    out_of_balance_flag boolean NOT NULL DEFAULT false,
    created_by_user_id uuid REFERENCES app_users(user_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS cost_allocation_lines (
    cost_allocation_line_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    cost_allocation_id uuid NOT NULL REFERENCES cost_allocations(cost_allocation_id) ON DELETE CASCADE,
    allocated_entity_type text NOT NULL,
    allocated_entity_id uuid NOT NULL,
    purchase_order_id uuid REFERENCES purchase_orders(purchase_order_id),
    purchase_order_line_id uuid REFERENCES purchase_order_lines(purchase_order_line_id),
    order_release_id uuid REFERENCES order_releases(order_release_id),
    order_release_line_id uuid REFERENCES order_release_lines(order_release_line_id),
    customer_party_id uuid REFERENCES parties(party_id),
    project_id uuid REFERENCES projects(project_id),
    cost_center_id uuid REFERENCES cost_centers(cost_center_id),
    gl_account_id uuid REFERENCES gl_accounts(gl_account_id),
    allocation_basis_quantity numeric(18, 6),
    allocation_percent numeric(8, 4),
    allocated_amount numeric(18, 2) NOT NULL,
    currency_id uuid REFERENCES lookup_values(lookup_value_id),
    adjustment_reason_id uuid REFERENCES lookup_values(lookup_value_id)
);

-- ---------------------------------------------------------------------------
-- Carrier invoice, freight audit, payable voucher, and payment
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS carrier_invoices (
    carrier_invoice_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    carrier_invoice_number text NOT NULL,
    carrier_id uuid NOT NULL REFERENCES carriers(carrier_id),
    invoice_type_id uuid REFERENCES lookup_values(lookup_value_id),
    invoice_date date NOT NULL,
    due_date date,
    currency_id uuid REFERENCES lookup_values(lookup_value_id),
    payment_terms_id uuid REFERENCES lookup_values(lookup_value_id),
    remittance_party_id uuid REFERENCES parties(party_id),
    invoice_total_amount numeric(18, 2) NOT NULL DEFAULT 0,
    tax_total_amount numeric(18, 2) NOT NULL DEFAULT 0,
    source_channel_id uuid REFERENCES lookup_values(lookup_value_id),
    source_system_id uuid REFERENCES external_systems(external_system_id),
    carrier_invoice_status_id uuid REFERENCES lookup_values(lookup_value_id),
    hold_flag boolean NOT NULL DEFAULT false,
    hold_reason_id uuid REFERENCES lookup_values(lookup_value_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (carrier_id, carrier_invoice_number)
);

CREATE TABLE IF NOT EXISTS carrier_invoice_lines (
    carrier_invoice_line_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    carrier_invoice_id uuid NOT NULL REFERENCES carrier_invoices(carrier_invoice_id) ON DELETE CASCADE,
    line_number text NOT NULL,
    shipment_id uuid REFERENCES shipments(shipment_id),
    load_id uuid REFERENCES loads(load_id),
    shipment_stop_id uuid REFERENCES shipment_stops(shipment_stop_id),
    order_release_id uuid REFERENCES order_releases(order_release_id),
    charge_id uuid REFERENCES charges(charge_id),
    charge_code_id uuid REFERENCES charge_codes(charge_code_id),
    description text,
    quantity numeric(18, 6),
    rate_amount numeric(18, 6),
    line_amount numeric(18, 2) NOT NULL DEFAULT 0,
    tax_amount numeric(18, 2) NOT NULL DEFAULT 0,
    line_status_id uuid REFERENCES lookup_values(lookup_value_id),
    UNIQUE (carrier_invoice_id, line_number)
);

CREATE TABLE IF NOT EXISTS freight_audit_results (
    freight_audit_result_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    carrier_invoice_id uuid REFERENCES carrier_invoices(carrier_invoice_id) ON DELETE CASCADE,
    carrier_invoice_line_id uuid REFERENCES carrier_invoice_lines(carrier_invoice_line_id) ON DELETE CASCADE,
    charge_id uuid REFERENCES charges(charge_id),
    audit_rule_id uuid REFERENCES business_rules(business_rule_id),
    audit_status_id uuid REFERENCES lookup_values(lookup_value_id),
    expected_amount numeric(18, 2),
    invoiced_amount numeric(18, 2),
    variance_amount numeric(18, 2),
    tolerance_amount numeric(18, 2),
    tolerance_percent numeric(8, 4),
    reason_code_id uuid REFERENCES lookup_values(lookup_value_id),
    disposition_id uuid REFERENCES lookup_values(lookup_value_id),
    approved_by_user_id uuid REFERENCES app_users(user_id),
    approved_at timestamptz,
    comments text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS disputes (
    dispute_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    dispute_number text NOT NULL UNIQUE,
    dispute_type_id uuid REFERENCES lookup_values(lookup_value_id),
    related_entity_type text NOT NULL,
    related_entity_id uuid NOT NULL,
    carrier_invoice_id uuid REFERENCES carrier_invoices(carrier_invoice_id),
    carrier_invoice_line_id uuid REFERENCES carrier_invoice_lines(carrier_invoice_line_id),
    client_bill_id uuid,
    dispute_reason_id uuid REFERENCES lookup_values(lookup_value_id),
    disputed_amount numeric(18, 2),
    currency_id uuid REFERENCES lookup_values(lookup_value_id),
    dispute_status_id uuid REFERENCES lookup_values(lookup_value_id),
    opened_by_user_id uuid REFERENCES app_users(user_id),
    opened_at timestamptz NOT NULL DEFAULT now(),
    resolved_at timestamptz,
    resolution_code_id uuid REFERENCES lookup_values(lookup_value_id),
    carrier_response text,
    notes text,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS vouchers (
    voucher_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    voucher_number text NOT NULL UNIQUE,
    carrier_invoice_id uuid REFERENCES carrier_invoices(carrier_invoice_id),
    payee_party_id uuid REFERENCES parties(party_id),
    voucher_date date NOT NULL,
    currency_id uuid REFERENCES lookup_values(lookup_value_id),
    voucher_total_amount numeric(18, 2) NOT NULL DEFAULT 0,
    voucher_status_id uuid REFERENCES lookup_values(lookup_value_id),
    exported_to_system_id uuid REFERENCES external_systems(external_system_id),
    exported_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS voucher_lines (
    voucher_line_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    voucher_id uuid NOT NULL REFERENCES vouchers(voucher_id) ON DELETE CASCADE,
    carrier_invoice_line_id uuid REFERENCES carrier_invoice_lines(carrier_invoice_line_id),
    charge_id uuid REFERENCES charges(charge_id),
    line_amount numeric(18, 2) NOT NULL,
    gl_account_id uuid REFERENCES gl_accounts(gl_account_id),
    cost_center_id uuid REFERENCES cost_centers(cost_center_id),
    line_status_id uuid REFERENCES lookup_values(lookup_value_id)
);

CREATE TABLE IF NOT EXISTS payments (
    payment_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    payment_number text NOT NULL UNIQUE,
    payment_type_id uuid REFERENCES lookup_values(lookup_value_id),
    payment_direction_id uuid REFERENCES lookup_values(lookup_value_id),
    payer_party_id uuid REFERENCES parties(party_id),
    payee_party_id uuid REFERENCES parties(party_id),
    voucher_id uuid REFERENCES vouchers(voucher_id),
    payment_source_type text,
    payment_source_id uuid,
    payment_date date,
    payment_amount numeric(18, 2) NOT NULL,
    currency_id uuid REFERENCES lookup_values(lookup_value_id),
    remittance_reference text,
    payment_status_id uuid REFERENCES lookup_values(lookup_value_id),
    source_system_id uuid REFERENCES external_systems(external_system_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Client billing, receivables, and margin
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS client_bills (
    client_bill_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    client_bill_number text NOT NULL UNIQUE,
    customer_party_id uuid NOT NULL REFERENCES parties(party_id),
    billing_account_id uuid REFERENCES parties(party_id),
    bill_type_id uuid REFERENCES lookup_values(lookup_value_id),
    bill_date date NOT NULL,
    due_date date,
    billing_period_start date,
    billing_period_end date,
    currency_id uuid REFERENCES lookup_values(lookup_value_id),
    tax_profile_id uuid REFERENCES lookup_values(lookup_value_id),
    payment_terms_id uuid REFERENCES lookup_values(lookup_value_id),
    total_bill_amount numeric(18, 2) NOT NULL DEFAULT 0,
    total_tax_amount numeric(18, 2) NOT NULL DEFAULT 0,
    client_bill_status_id uuid REFERENCES lookup_values(lookup_value_id),
    hold_flag boolean NOT NULL DEFAULT false,
    hold_reason_id uuid REFERENCES lookup_values(lookup_value_id),
    exported_to_system_id uuid REFERENCES external_systems(external_system_id),
    exported_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS client_bill_lines (
    client_bill_line_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    client_bill_id uuid NOT NULL REFERENCES client_bills(client_bill_id) ON DELETE CASCADE,
    line_number text NOT NULL,
    shipment_id uuid REFERENCES shipments(shipment_id),
    load_id uuid REFERENCES loads(load_id),
    order_release_id uuid REFERENCES order_releases(order_release_id),
    purchase_order_id uuid REFERENCES purchase_orders(purchase_order_id),
    purchase_order_line_id uuid REFERENCES purchase_order_lines(purchase_order_line_id),
    charge_id uuid REFERENCES charges(charge_id),
    cost_allocation_line_id uuid REFERENCES cost_allocation_lines(cost_allocation_line_id),
    charge_code_id uuid REFERENCES charge_codes(charge_code_id),
    description text,
    quantity numeric(18, 6),
    rate_amount numeric(18, 6),
    cost_amount numeric(18, 2),
    markup_amount numeric(18, 2),
    margin_amount numeric(18, 2),
    line_amount numeric(18, 2) NOT NULL DEFAULT 0,
    tax_amount numeric(18, 2) NOT NULL DEFAULT 0,
    line_status_id uuid REFERENCES lookup_values(lookup_value_id),
    UNIQUE (client_bill_id, line_number)
);

CREATE TABLE IF NOT EXISTS client_bill_payments (
    client_bill_payment_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    client_bill_id uuid NOT NULL REFERENCES client_bills(client_bill_id) ON DELETE CASCADE,
    payment_id uuid REFERENCES payments(payment_id),
    received_amount numeric(18, 2) NOT NULL,
    currency_id uuid REFERENCES lookup_values(lookup_value_id),
    received_date date,
    settlement_status_id uuid REFERENCES lookup_values(lookup_value_id),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS credits_and_adjustments (
    credit_adjustment_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    adjustment_number text NOT NULL UNIQUE,
    adjustment_type_id uuid REFERENCES lookup_values(lookup_value_id),
    client_bill_id uuid REFERENCES client_bills(client_bill_id),
    carrier_invoice_id uuid REFERENCES carrier_invoices(carrier_invoice_id),
    charge_id uuid REFERENCES charges(charge_id),
    adjustment_amount numeric(18, 2) NOT NULL,
    currency_id uuid REFERENCES lookup_values(lookup_value_id),
    reason_code_id uuid REFERENCES lookup_values(lookup_value_id),
    status_id uuid REFERENCES lookup_values(lookup_value_id),
    created_by_user_id uuid REFERENCES app_users(user_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Accruals, accounting, tax, and financial reconciliation
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS financial_periods (
    financial_period_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    period_code text NOT NULL UNIQUE,
    period_start_date date NOT NULL,
    period_end_date date NOT NULL,
    close_status_id uuid REFERENCES lookup_values(lookup_value_id),
    closed_at timestamptz,
    closed_by_user_id uuid REFERENCES app_users(user_id)
);

CREATE TABLE IF NOT EXISTS exchange_rates (
    exchange_rate_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    from_currency_id uuid NOT NULL REFERENCES lookup_values(lookup_value_id),
    to_currency_id uuid NOT NULL REFERENCES lookup_values(lookup_value_id),
    rate_date date NOT NULL,
    exchange_rate numeric(24, 12) NOT NULL CHECK (exchange_rate > 0),
    source_system_id uuid REFERENCES external_systems(external_system_id),
    UNIQUE (from_currency_id, to_currency_id, rate_date)
);

CREATE TABLE IF NOT EXISTS tax_rules (
    tax_rule_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tax_rule_code text NOT NULL UNIQUE,
    tax_jurisdiction_id uuid REFERENCES lookup_values(lookup_value_id),
    charge_code_id uuid REFERENCES charge_codes(charge_code_id),
    rate_percent numeric(8, 4),
    condition_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    status_id uuid REFERENCES lookup_values(lookup_value_id),
    effective_start_date date,
    effective_end_date date
);

CREATE TABLE IF NOT EXISTS accruals (
    accrual_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    accrual_number text NOT NULL UNIQUE,
    accrual_source_type text NOT NULL,
    accrual_source_id uuid NOT NULL,
    shipment_id uuid REFERENCES shipments(shipment_id),
    load_id uuid REFERENCES loads(load_id),
    charge_id uuid REFERENCES charges(charge_id),
    financial_period_id uuid REFERENCES financial_periods(financial_period_id),
    accrual_milestone_id uuid REFERENCES lookup_values(lookup_value_id),
    accrual_amount numeric(18, 2) NOT NULL,
    currency_id uuid REFERENCES lookup_values(lookup_value_id),
    accrual_status_id uuid REFERENCES lookup_values(lookup_value_id),
    reversed_accrual_id uuid REFERENCES accruals(accrual_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS accounting_distributions (
    accounting_distribution_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    distribution_source_type text NOT NULL,
    distribution_source_id uuid NOT NULL,
    charge_id uuid REFERENCES charges(charge_id),
    voucher_id uuid REFERENCES vouchers(voucher_id),
    client_bill_id uuid REFERENCES client_bills(client_bill_id),
    accrual_id uuid REFERENCES accruals(accrual_id),
    business_unit_id uuid REFERENCES business_units(business_unit_id),
    gl_account_id uuid REFERENCES gl_accounts(gl_account_id),
    cost_center_id uuid REFERENCES cost_centers(cost_center_id),
    project_id uuid REFERENCES projects(project_id),
    debit_amount numeric(18, 2) NOT NULL DEFAULT 0,
    credit_amount numeric(18, 2) NOT NULL DEFAULT 0,
    currency_id uuid REFERENCES lookup_values(lookup_value_id),
    distribution_status_id uuid REFERENCES lookup_values(lookup_value_id),
    exported_to_system_id uuid REFERENCES external_systems(external_system_id),
    exported_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS financial_reconciliations (
    financial_reconciliation_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    reconciliation_number text NOT NULL UNIQUE,
    shipment_id uuid REFERENCES shipments(shipment_id),
    load_id uuid REFERENCES loads(load_id),
    planned_cost_amount numeric(18, 2) DEFAULT 0,
    tendered_cost_amount numeric(18, 2) DEFAULT 0,
    accrued_cost_amount numeric(18, 2) DEFAULT 0,
    actual_carrier_cost_amount numeric(18, 2) DEFAULT 0,
    approved_payable_amount numeric(18, 2) DEFAULT 0,
    paid_amount numeric(18, 2) DEFAULT 0,
    client_bill_amount numeric(18, 2) DEFAULT 0,
    received_amount numeric(18, 2) DEFAULT 0,
    margin_amount numeric(18, 2) DEFAULT 0,
    currency_id uuid REFERENCES lookup_values(lookup_value_id),
    reconciliation_status_id uuid REFERENCES lookup_values(lookup_value_id),
    reconciled_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Exceptions, claims, appointments, yard, dock, and gate
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS exceptions (
    exception_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    exception_number text NOT NULL UNIQUE,
    exception_type_id uuid REFERENCES lookup_values(lookup_value_id),
    related_entity_type text NOT NULL,
    related_entity_id uuid NOT NULL,
    severity_id uuid REFERENCES lookup_values(lookup_value_id),
    owner_user_id uuid REFERENCES app_users(user_id),
    owner_role_id uuid REFERENCES roles(role_id),
    due_at timestamptz,
    sla_minutes integer,
    root_cause_id uuid REFERENCES lookup_values(lookup_value_id),
    resolution_code_id uuid REFERENCES lookup_values(lookup_value_id),
    exception_status_id uuid REFERENCES lookup_values(lookup_value_id),
    blocking_flag boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    resolved_at timestamptz
);

CREATE TABLE IF NOT EXISTS claims (
    claim_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    claim_number text NOT NULL UNIQUE,
    claim_type_id uuid REFERENCES lookup_values(lookup_value_id),
    shipment_id uuid REFERENCES shipments(shipment_id),
    carrier_id uuid REFERENCES carriers(carrier_id),
    customer_party_id uuid REFERENCES parties(party_id),
    claim_amount numeric(18, 2),
    recovery_amount numeric(18, 2),
    currency_id uuid REFERENCES lookup_values(lookup_value_id),
    claimed_quantity numeric(18, 6),
    damaged_quantity numeric(18, 6),
    claim_status_id uuid REFERENCES lookup_values(lookup_value_id),
    submitted_at timestamptz,
    settled_at timestamptz,
    notes text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS facility_calendars (
    facility_calendar_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id uuid NOT NULL REFERENCES locations(location_id),
    calendar_name text NOT NULL,
    time_zone text,
    operating_hours_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    blackout_dates_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    status_id uuid REFERENCES lookup_values(lookup_value_id)
);

CREATE TABLE IF NOT EXISTS dock_doors (
    dock_door_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id uuid NOT NULL REFERENCES locations(location_id),
    dock_door_code text NOT NULL,
    dock_door_name text,
    equipment_restrictions_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    status_id uuid REFERENCES lookup_values(lookup_value_id),
    UNIQUE (location_id, dock_door_code)
);

CREATE TABLE IF NOT EXISTS appointments (
    appointment_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    appointment_number text NOT NULL UNIQUE,
    shipment_stop_id uuid REFERENCES shipment_stops(shipment_stop_id),
    location_id uuid NOT NULL REFERENCES locations(location_id),
    dock_door_id uuid REFERENCES dock_doors(dock_door_id),
    carrier_id uuid REFERENCES carriers(carrier_id),
    appointment_start_datetime timestamptz NOT NULL,
    appointment_end_datetime timestamptz,
    appointment_status_id uuid REFERENCES lookup_values(lookup_value_id),
    confirmation_number text,
    created_by_user_id uuid REFERENCES app_users(user_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS gate_transactions (
    gate_transaction_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    gate_transaction_number text NOT NULL UNIQUE,
    location_id uuid NOT NULL REFERENCES locations(location_id),
    appointment_id uuid REFERENCES appointments(appointment_id),
    shipment_id uuid REFERENCES shipments(shipment_id),
    load_id uuid REFERENCES loads(load_id),
    carrier_id uuid REFERENCES carriers(carrier_id),
    driver_name text,
    tractor_number text,
    trailer_number text,
    container_number text,
    chassis_number text,
    seal_number text,
    check_in_at timestamptz,
    check_out_at timestamptz,
    gate_status_id uuid REFERENCES lookup_values(lookup_value_id),
    notes text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS yard_locations (
    yard_location_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id uuid NOT NULL REFERENCES locations(location_id),
    yard_location_code text NOT NULL,
    yard_location_type_id uuid REFERENCES lookup_values(lookup_value_id),
    capacity_quantity numeric(18, 6),
    status_id uuid REFERENCES lookup_values(lookup_value_id),
    UNIQUE (location_id, yard_location_code)
);

CREATE TABLE IF NOT EXISTS yard_moves (
    yard_move_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    yard_move_number text NOT NULL UNIQUE,
    gate_transaction_id uuid REFERENCES gate_transactions(gate_transaction_id),
    from_yard_location_id uuid REFERENCES yard_locations(yard_location_id),
    to_yard_location_id uuid REFERENCES yard_locations(yard_location_id),
    asset_type_id uuid REFERENCES lookup_values(lookup_value_id),
    asset_identifier text NOT NULL,
    move_status_id uuid REFERENCES lookup_values(lookup_value_id),
    requested_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    created_by_user_id uuid REFERENCES app_users(user_id)
);

-- ---------------------------------------------------------------------------
-- Documents, integrations, workflow, reporting, and traceability
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS documents (
    document_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_number text NOT NULL UNIQUE,
    document_type_id uuid REFERENCES lookup_values(lookup_value_id),
    document_name text NOT NULL,
    document_status_id uuid REFERENCES lookup_values(lookup_value_id),
    storage_uri text,
    content_hash text,
    version_number integer NOT NULL DEFAULT 1,
    owner_party_id uuid REFERENCES parties(party_id),
    uploaded_by_user_id uuid REFERENCES app_users(user_id),
    retention_policy_id uuid REFERENCES lookup_values(lookup_value_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS document_links (
    document_link_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id uuid NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    related_entity_type text NOT NULL,
    related_entity_id uuid NOT NULL,
    link_role_id uuid REFERENCES lookup_values(lookup_value_id),
    required_flag boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (document_id, related_entity_type, related_entity_id, link_role_id)
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_carrier_compliance_document'
          AND conrelid = 'carrier_compliance_records'::regclass
    ) THEN
        ALTER TABLE carrier_compliance_records
            ADD CONSTRAINT fk_carrier_compliance_document
            FOREIGN KEY (document_id) REFERENCES documents(document_id);
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS document_templates (
    document_template_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    template_code text NOT NULL UNIQUE,
    document_type_id uuid REFERENCES lookup_values(lookup_value_id),
    applies_to_entity text,
    condition_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    template_uri text,
    status_id uuid REFERENCES lookup_values(lookup_value_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS integration_transactions (
    integration_transaction_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    external_system_id uuid NOT NULL REFERENCES external_systems(external_system_id),
    transaction_direction_id uuid REFERENCES lookup_values(lookup_value_id),
    transaction_type text NOT NULL,
    transaction_set text,
    related_entity_type text,
    related_entity_id uuid,
    correlation_id text,
    payload_uri text,
    acknowledgement_reference text,
    transaction_status_id uuid REFERENCES lookup_values(lookup_value_id),
    error_message text,
    retry_count integer NOT NULL DEFAULT 0,
    received_at timestamptz,
    sent_at timestamptz,
    processed_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS integration_mappings (
    integration_mapping_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    external_system_id uuid NOT NULL REFERENCES external_systems(external_system_id),
    mapping_code text NOT NULL,
    source_entity text NOT NULL,
    target_entity text NOT NULL,
    mapping_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    status_id uuid REFERENCES lookup_values(lookup_value_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (external_system_id, mapping_code)
);

CREATE TABLE IF NOT EXISTS workflow_definitions (
    workflow_definition_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_code text NOT NULL UNIQUE,
    workflow_name text NOT NULL,
    applies_to_entity text NOT NULL,
    workflow_type_id uuid REFERENCES lookup_values(lookup_value_id),
    condition_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    version_number integer NOT NULL DEFAULT 1,
    status_id uuid REFERENCES lookup_values(lookup_value_id),
    effective_start_date date,
    effective_end_date date,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS workflow_steps (
    workflow_step_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_definition_id uuid NOT NULL REFERENCES workflow_definitions(workflow_definition_id) ON DELETE CASCADE,
    step_sequence integer NOT NULL,
    step_name text NOT NULL,
    approval_role_id uuid REFERENCES roles(role_id),
    approval_user_id uuid REFERENCES app_users(user_id),
    escalation_minutes integer,
    condition_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (workflow_definition_id, step_sequence)
);

CREATE TABLE IF NOT EXISTS approval_requests (
    approval_request_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_definition_id uuid REFERENCES workflow_definitions(workflow_definition_id),
    workflow_step_id uuid REFERENCES workflow_steps(workflow_step_id),
    related_entity_type text NOT NULL,
    related_entity_id uuid NOT NULL,
    requested_by_user_id uuid REFERENCES app_users(user_id),
    approver_user_id uuid REFERENCES app_users(user_id),
    approver_role_id uuid REFERENCES roles(role_id),
    approval_status_id uuid REFERENCES lookup_values(lookup_value_id),
    requested_at timestamptz NOT NULL DEFAULT now(),
    decided_at timestamptz,
    decision_reason_id uuid REFERENCES lookup_values(lookup_value_id),
    original_value_json jsonb,
    approved_value_json jsonb,
    comments text
);

CREATE TABLE IF NOT EXISTS dashboards (
    dashboard_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    dashboard_code text NOT NULL UNIQUE,
    dashboard_name text NOT NULL,
    dashboard_type_id uuid REFERENCES lookup_values(lookup_value_id),
    owner_user_id uuid REFERENCES app_users(user_id),
    owner_role_id uuid REFERENCES roles(role_id),
    layout_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    status_id uuid REFERENCES lookup_values(lookup_value_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS saved_views (
    saved_view_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    view_code text NOT NULL UNIQUE,
    view_name text NOT NULL,
    entity_type text NOT NULL,
    owner_user_id uuid REFERENCES app_users(user_id),
    owner_role_id uuid REFERENCES roles(role_id),
    filter_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    column_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    sort_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS work_queue_items (
    work_queue_item_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    queue_name text NOT NULL,
    related_entity_type text NOT NULL,
    related_entity_id uuid NOT NULL,
    priority_id uuid REFERENCES lookup_values(lookup_value_id),
    owner_user_id uuid REFERENCES app_users(user_id),
    owner_role_id uuid REFERENCES roles(role_id),
    due_at timestamptz,
    work_status_id uuid REFERENCES lookup_values(lookup_value_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS notifications (
    notification_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    notification_type_id uuid REFERENCES lookup_values(lookup_value_id),
    recipient_user_id uuid REFERENCES app_users(user_id),
    recipient_party_id uuid REFERENCES parties(party_id),
    related_entity_type text,
    related_entity_id uuid,
    channel_id uuid REFERENCES lookup_values(lookup_value_id),
    subject text,
    message_text text,
    sent_at timestamptz,
    read_at timestamptz,
    notification_status_id uuid REFERENCES lookup_values(lookup_value_id),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audit_logs (
    audit_log_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type text NOT NULL,
    entity_id uuid NOT NULL,
    action_id uuid REFERENCES lookup_values(lookup_value_id),
    changed_by_user_id uuid REFERENCES app_users(user_id),
    changed_at timestamptz NOT NULL DEFAULT now(),
    old_value_json jsonb,
    new_value_json jsonb,
    source_system_id uuid REFERENCES external_systems(external_system_id),
    reason_code_id uuid REFERENCES lookup_values(lookup_value_id),
    comments text
);

CREATE TABLE IF NOT EXISTS traceability_links (
    traceability_link_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    from_entity_type text NOT NULL,
    from_entity_id uuid NOT NULL,
    to_entity_type text NOT NULL,
    to_entity_id uuid NOT NULL,
    link_type_id uuid REFERENCES lookup_values(lookup_value_id),
    source_system_id uuid REFERENCES external_systems(external_system_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (from_entity_type, from_entity_id, to_entity_type, to_entity_id, link_type_id)
);

CREATE TABLE IF NOT EXISTS reference_numbers (
    reference_number_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type text NOT NULL,
    entity_id uuid NOT NULL,
    reference_type_id uuid REFERENCES lookup_values(lookup_value_id),
    reference_value text NOT NULL,
    source_system_id uuid REFERENCES external_systems(external_system_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (entity_type, reference_type_id, reference_value, source_system_id)
);

-- ---------------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_lookup_values_type_code ON lookup_values (lookup_type_id, lookup_code);
CREATE INDEX IF NOT EXISTS idx_parties_type_status ON parties (party_type_id, status_id);
CREATE INDEX IF NOT EXISTS idx_locations_party ON locations (party_id);
CREATE INDEX IF NOT EXISTS idx_locations_type_status ON locations (location_type_id, status_id);
CREATE INDEX IF NOT EXISTS idx_external_references_entity ON external_references (entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_items_commodity ON items (commodity_id);
CREATE INDEX IF NOT EXISTS idx_carriers_status ON carriers (status_id);
CREATE INDEX IF NOT EXISTS idx_carrier_services_carrier ON carrier_services (carrier_id, transport_mode_id, service_level_id);
CREATE INDEX IF NOT EXISTS idx_purchase_orders_supplier_status ON purchase_orders (supplier_party_id, status_id);
CREATE INDEX IF NOT EXISTS idx_purchase_orders_buyer_status ON purchase_orders (buyer_party_id, status_id);
CREATE INDEX IF NOT EXISTS idx_purchase_order_lines_order ON purchase_order_lines (purchase_order_id, status_id);
CREATE INDEX IF NOT EXISTS idx_purchase_order_lines_item ON purchase_order_lines (item_id);
CREATE INDEX IF NOT EXISTS idx_order_releases_status ON order_releases (status_id);
CREATE INDEX IF NOT EXISTS idx_order_releases_po ON order_releases (source_purchase_order_id);
CREATE INDEX IF NOT EXISTS idx_order_release_lines_release ON order_release_lines (order_release_id);
CREATE INDEX IF NOT EXISTS idx_order_release_lines_po_line ON order_release_lines (purchase_order_line_id);
CREATE INDEX IF NOT EXISTS idx_loads_status ON loads (status_id);
CREATE INDEX IF NOT EXISTS idx_shipments_status ON shipments (shipment_status_id);
CREATE INDEX IF NOT EXISTS idx_shipments_carrier ON shipments (carrier_id);
CREATE INDEX IF NOT EXISTS idx_shipments_locations ON shipments (origin_location_id, destination_location_id);
CREATE INDEX IF NOT EXISTS idx_load_shipments_shipment ON load_shipments (shipment_id);
CREATE INDEX IF NOT EXISTS idx_shipment_lines_shipment ON shipment_lines (shipment_id);
CREATE INDEX IF NOT EXISTS idx_shipment_lines_release_line ON shipment_lines (order_release_line_id);
CREATE INDEX IF NOT EXISTS idx_shipment_stops_shipment_sequence ON shipment_stops (shipment_id, stop_sequence);
CREATE INDEX IF NOT EXISTS idx_shipment_stops_location_time ON shipment_stops (location_id, planned_arrival_datetime);
CREATE INDEX IF NOT EXISTS idx_stop_activities_stop_status ON stop_activities (shipment_stop_id, activity_status_id);
CREATE INDEX IF NOT EXISTS idx_tracking_events_shipment_time ON tracking_events (shipment_id, event_datetime DESC);
CREATE INDEX IF NOT EXISTS idx_milestones_shipment_status ON milestones (shipment_id, milestone_status_id);
CREATE INDEX IF NOT EXISTS idx_tenders_shipment ON tenders (shipment_id, tender_status_id);
CREATE INDEX IF NOT EXISTS idx_tenders_load ON tenders (load_id, tender_status_id);
CREATE INDEX IF NOT EXISTS idx_rate_rules_contract ON rate_rules (rate_contract_id, charge_code_id);
CREATE INDEX IF NOT EXISTS idx_charges_source ON charges (charge_source_type, charge_source_id);
CREATE INDEX IF NOT EXISTS idx_charges_shipment ON charges (shipment_id, charge_status_id);
CREATE INDEX IF NOT EXISTS idx_cost_allocations_charge ON cost_allocations (charge_id, allocation_status_id);
CREATE INDEX IF NOT EXISTS idx_cost_allocation_lines_entity ON cost_allocation_lines (allocated_entity_type, allocated_entity_id);
CREATE INDEX IF NOT EXISTS idx_carrier_invoices_carrier_status ON carrier_invoices (carrier_id, carrier_invoice_status_id);
CREATE INDEX IF NOT EXISTS idx_carrier_invoice_lines_invoice ON carrier_invoice_lines (carrier_invoice_id);
CREATE INDEX IF NOT EXISTS idx_freight_audit_results_invoice ON freight_audit_results (carrier_invoice_id, audit_status_id);
CREATE INDEX IF NOT EXISTS idx_disputes_entity ON disputes (related_entity_type, related_entity_id);
CREATE INDEX IF NOT EXISTS idx_vouchers_invoice ON vouchers (carrier_invoice_id, voucher_status_id);
CREATE INDEX IF NOT EXISTS idx_payments_source ON payments (payment_source_type, payment_source_id);
CREATE INDEX IF NOT EXISTS idx_client_bills_customer_status ON client_bills (customer_party_id, client_bill_status_id);
CREATE INDEX IF NOT EXISTS idx_client_bill_lines_bill ON client_bill_lines (client_bill_id);
CREATE INDEX IF NOT EXISTS idx_accruals_source ON accruals (accrual_source_type, accrual_source_id);
CREATE INDEX IF NOT EXISTS idx_accounting_distributions_source ON accounting_distributions (distribution_source_type, distribution_source_id);
CREATE INDEX IF NOT EXISTS idx_exceptions_entity_status ON exceptions (related_entity_type, related_entity_id, exception_status_id);
CREATE INDEX IF NOT EXISTS idx_claims_shipment_status ON claims (shipment_id, claim_status_id);
CREATE INDEX IF NOT EXISTS idx_appointments_location_time ON appointments (location_id, appointment_start_datetime);
CREATE INDEX IF NOT EXISTS idx_gate_transactions_location_time ON gate_transactions (location_id, check_in_at);
CREATE INDEX IF NOT EXISTS idx_documents_type_status ON documents (document_type_id, document_status_id);
CREATE INDEX IF NOT EXISTS idx_document_links_entity ON document_links (related_entity_type, related_entity_id);
CREATE INDEX IF NOT EXISTS idx_integration_transactions_status ON integration_transactions (external_system_id, transaction_status_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_approval_requests_entity ON approval_requests (related_entity_type, related_entity_id, approval_status_id);
CREATE INDEX IF NOT EXISTS idx_work_queue_items_owner ON work_queue_items (owner_user_id, owner_role_id, work_status_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_entity ON audit_logs (entity_type, entity_id, changed_at DESC);
CREATE INDEX IF NOT EXISTS idx_traceability_from ON traceability_links (from_entity_type, from_entity_id);
CREATE INDEX IF NOT EXISTS idx_traceability_to ON traceability_links (to_entity_type, to_entity_id);
CREATE INDEX IF NOT EXISTS idx_reference_numbers_value ON reference_numbers (reference_value);

-- ---------------------------------------------------------------------------
-- Updated-at triggers for tables that have updated_at
-- ---------------------------------------------------------------------------

DO $$
DECLARE
    target_table text;
BEGIN
    FOREACH target_table IN ARRAY ARRAY[
        'lookup_types', 'lookup_values', 'status_models', 'numbering_schemes',
        'business_rules', 'validation_rules', 'organizations', 'business_units',
        'parties', 'contacts', 'locations', 'external_systems', 'app_users',
        'roles', 'items', 'carriers', 'carrier_compliance_records',
        'purchase_orders', 'purchase_order_lines', 'release_rules',
        'order_releases', 'order_release_lines', 'loads', 'shipments',
        'shipment_lines', 'shipment_stops', 'stop_activities', 'milestones',
        'rate_contracts', 'charges', 'cost_allocations', 'carrier_invoices',
        'vouchers', 'payments', 'client_bills', 'credits_and_adjustments',
        'accruals', 'financial_reconciliations', 'exceptions', 'claims',
        'appointments', 'gate_transactions', 'documents', 'document_templates',
        'integration_mappings', 'workflow_definitions', 'dashboards',
        'saved_views', 'work_queue_items'
    ]
    LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS %I ON %I', 'trg_' || target_table || '_touch_updated_at', target_table);
        EXECUTE format(
            'CREATE TRIGGER %I BEFORE UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION touch_updated_at()',
            'trg_' || target_table || '_touch_updated_at',
            target_table
        );
    END LOOP;
END;
$$;

-- ---------------------------------------------------------------------------
-- Comments
-- ---------------------------------------------------------------------------

COMMENT ON SCHEMA tms IS 'Flow Ops TMS schema — adapted from enterprise_tms_functional_requirements.docx for Flow Ops Global LLC.';
COMMENT ON TABLE functional_requirements IS 'Traceability store for functional requirements from the source Word document.';
COMMENT ON TABLE purchase_orders IS 'PO header received from ERP, supplier portal, EDI, API, spreadsheet, or manual entry.';
COMMENT ON TABLE purchase_order_lines IS 'Item-level PO demand with releasable, released, planned, shipped, delivered, received, canceled, and remaining quantities.';
COMMENT ON TABLE order_releases IS 'Transportation-ready demand created from PO lines or external demand.';
COMMENT ON TABLE shipments IS 'Planned transportation movement that can contain multiple releases, PO lines, customers, suppliers, and cost owners.';
COMMENT ON TABLE loads IS 'Execution or tendering unit that can consolidate multiple shipments.';
COMMENT ON TABLE shipment_stops IS 'Pickup, delivery, cross-dock, terminal, port, yard, or intermediate execution stop.';
COMMENT ON TABLE stop_activities IS 'Required, optional, or conditional operational tasks captured at a stop.';
COMMENT ON TABLE tenders IS 'Carrier tender offer, response, expiration, retender, and award tracking.';
COMMENT ON TABLE charges IS 'Financial charge line for freight, fuel, accessorial, tax, duty, adjustment, discount, credit, fee, or surcharge.';
COMMENT ON TABLE cost_allocations IS 'Allocation header for distributing shipment or charge cost across PO, order, customer, project, cost center, and GL structures.';
COMMENT ON TABLE carrier_invoices IS 'Carrier invoice header for freight audit, payable voucher, payment, and aging.';
COMMENT ON TABLE freight_audit_results IS 'Line-level freight audit variance, tolerance, disposition, and approval result.';
COMMENT ON TABLE client_bills IS 'Customer/client bill independent from carrier invoice timing.';
COMMENT ON TABLE financial_reconciliations IS 'Reconciliation across planned, tendered, accrued, invoiced, payable, paid, billed, received, and margin amounts.';
COMMENT ON TABLE traceability_links IS 'Generic end-to-end chain between PO, PO line, release, shipment, stop, charge, invoice, bill, voucher, payment, document, claim, and audit records.';


-- ---------------------------------------------------------------------------
-- Flow Ops TMS — OMS Integration & Numbering additions
-- (these tables are specific to Flow Ops and not in the enterprise schema)
-- ---------------------------------------------------------------------------

-- Idempotent log of every OMS event consumed by the TMS.
-- Prevents double-processing on retry.
CREATE TABLE IF NOT EXISTS oms_event_log (
    log_id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    oms_event_id            uuid NOT NULL UNIQUE,
    event_type              text NOT NULL,
    event_payload           jsonb NOT NULL DEFAULT '{}'::jsonb,
    processed_at            timestamptz NOT NULL DEFAULT now(),
    result                  text NOT NULL DEFAULT 'OK',   -- OK | FAILED | SKIPPED
    error_message           text,
    created_entity_type     text,
    created_entity_id       uuid
);

CREATE INDEX IF NOT EXISTS idx_oms_event_log_type_time
    ON oms_event_log (event_type, processed_at DESC);

-- ---------------------------------------------------------------------------
-- Sequences for human-readable document numbers
-- ---------------------------------------------------------------------------

CREATE SEQUENCE IF NOT EXISTS seq_shipment_number  START 1;
CREATE SEQUENCE IF NOT EXISTS seq_load_number      START 1;
CREATE SEQUENCE IF NOT EXISTS seq_release_number   START 1;
CREATE SEQUENCE IF NOT EXISTS seq_tender_number    START 1;
CREATE SEQUENCE IF NOT EXISTS seq_charge_number    START 1;
CREATE SEQUENCE IF NOT EXISTS seq_invoice_number   START 1;
CREATE SEQUENCE IF NOT EXISTS seq_voucher_number   START 1;
CREATE SEQUENCE IF NOT EXISTS seq_payment_number   START 1;
CREATE SEQUENCE IF NOT EXISTS seq_bill_number      START 1;
CREATE SEQUENCE IF NOT EXISTS seq_claim_number     START 1;
CREATE SEQUENCE IF NOT EXISTS seq_exception_number START 1;
CREATE SEQUENCE IF NOT EXISTS seq_appt_number      START 1;
CREATE SEQUENCE IF NOT EXISTS seq_gate_number      START 1;
CREATE SEQUENCE IF NOT EXISTS seq_doc_number       START 1;
CREATE SEQUENCE IF NOT EXISTS seq_dispute_number   START 1;
CREATE SEQUENCE IF NOT EXISTS seq_accrual_number   START 1;
CREATE SEQUENCE IF NOT EXISTS seq_recon_number     START 1;
CREATE SEQUENCE IF NOT EXISTS seq_alloc_number     START 1;
CREATE SEQUENCE IF NOT EXISTS seq_rating_number    START 1;

CREATE OR REPLACE FUNCTION next_doc_number(prefix text, seq regclass)
RETURNS text LANGUAGE sql AS $$
    SELECT prefix || lpad(nextval(seq)::text, 6, '0')
$$;


COMMIT;
