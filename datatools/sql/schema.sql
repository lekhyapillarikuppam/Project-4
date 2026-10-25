-- Reference data tables (001 Plan §3). The loader runs this inside its transaction and may substitute
-- the schema name `ref` (for example `ref_test` in the rollback test, DATA-AT-04).

CREATE SCHEMA IF NOT EXISTS ref;

CREATE TABLE IF NOT EXISTS ref.data_version (version text PRIMARY KEY, compiled text NOT NULL,
  loaded_at timestamptz NOT NULL DEFAULT now());

CREATE TABLE IF NOT EXISTS ref.cities (city_id char(3) PRIMARY KEY, name text NOT NULL, lat numeric(8,5), lon numeric(8,5),
  traffic_factor numeric(3,2) NOT NULL, food_multiplier numeric(3,2) NOT NULL, source text NOT NULL, checked_on date NOT NULL);

CREATE TABLE IF NOT EXISTS ref.hubs (city_id char(3) REFERENCES ref.cities, mode text CHECK (mode IN ('train','bus','flight')),
  hub_name text NOT NULL, hub_code text, lat numeric(8,5), lon numeric(8,5), access_km numeric(6,1) NOT NULL,
  access_minutes int NOT NULL, access_cost_per_vehicle int NOT NULL, source text NOT NULL, checked_on date NOT NULL,
  PRIMARY KEY (city_id, mode));

-- 210 directed rows, expanded from the 105 unordered CSV rows
CREATE TABLE IF NOT EXISTS ref.city_pairs (from_city char(3) REFERENCES ref.cities, to_city char(3) REFERENCES ref.cities,
  road_km numeric(7,1), rail_km numeric(7,1), air_km numeric(7,1),
  train_available bool NOT NULL, bus_available bool NOT NULL, flight_available bool NOT NULL,
  train_minutes int, bus_minutes int, flight_minutes int, rail_km_approx bool NOT NULL,
  train_minutes_approx bool NOT NULL, bus_minutes_approx bool NOT NULL, flight_minutes_approx bool NOT NULL,
  source text NOT NULL, checked_on date NOT NULL, PRIMARY KEY (from_city, to_city));

CREATE TABLE IF NOT EXISTS ref.fare_rates (mode text, class text, base_fare int NOT NULL, per_km numeric(5,2) NOT NULL,
  min_fare int NOT NULL, comfort_value numeric(3,2) NOT NULL, source text NOT NULL, checked_on date NOT NULL,
  PRIMARY KEY (mode, class));

CREATE TABLE IF NOT EXISTS ref.attractions (attraction_id text PRIMARY KEY, city_id char(3) REFERENCES ref.cities, name text NOT NULL,
  lat numeric(8,5), lon numeric(8,5), visit_minutes int NOT NULL, visit_approx bool NOT NULL,
  open_time time NOT NULL, close_time time NOT NULL, closed_weekdays int[] NOT NULL, hours_approx bool NOT NULL,
  entry_fee int NOT NULL, fee_approx bool NOT NULL, tags text[] NOT NULL, rating numeric(2,1) NOT NULL,
  outdoor bool NOT NULL, crowd_level text NOT NULL, fixed_slot bool NOT NULL, source text NOT NULL, checked_on date NOT NULL);

CREATE TABLE IF NOT EXISTS ref.hotels (hotel_id text PRIMARY KEY, city_id char(3) REFERENCES ref.cities, name text NOT NULL,
  tier text NOT NULL, lat numeric(8,5), lon numeric(8,5), price_per_room_night int NOT NULL,
  source text NOT NULL, checked_on date NOT NULL);

CREATE TABLE IF NOT EXISTS ref.food (comfort text PRIMARY KEY, base_per_person_per_day int NOT NULL, source text NOT NULL,
  checked_on date NOT NULL);

CREATE TABLE IF NOT EXISTS ref.local_transport (city_id char(3) REFERENCES ref.cities, mode text, min_fare int NOT NULL,
  min_km numeric(4,1) NOT NULL, per_km numeric(5,2) NOT NULL, capacity int NOT NULL, approx bool NOT NULL,
  source text NOT NULL, checked_on date NOT NULL,
  PRIMARY KEY (city_id, mode));

-- matrices stored long-form
CREATE TABLE IF NOT EXISTS ref.travel_matrix (city_id char(3) REFERENCES ref.cities, from_node text, to_node text,
  km numeric(6,1) NOT NULL, minutes_free_flow int NOT NULL, PRIMARY KEY (city_id, from_node, to_node));
