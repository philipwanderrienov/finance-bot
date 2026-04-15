-- public.scheduler_jobs definition

-- Drop table

-- DROP TABLE public.scheduler_jobs;

CREATE TABLE public.scheduler_jobs (
	id bigserial NOT NULL,
	job_name text NOT NULL,
	service_name text NOT NULL,
	enabled bool DEFAULT true NOT NULL,
	schedule_type text NOT NULL,
	schedule_value text NOT NULL,
	timezone text DEFAULT 'UTC'::text NOT NULL,
	last_run_at timestamptz NULL,
	next_run_at timestamptz NULL,
	last_status text NULL,
	retry_count int4 DEFAULT 0 NOT NULL,
	max_retries int4 DEFAULT 3 NOT NULL,
	created_at timestamptz DEFAULT now() NOT NULL,
	updated_at timestamptz DEFAULT now() NOT NULL,
	CONSTRAINT scheduler_jobs_job_name_key UNIQUE (job_name),
	CONSTRAINT scheduler_jobs_max_retries_check CHECK ((max_retries >= 0)),
	CONSTRAINT scheduler_jobs_pkey PRIMARY KEY (id),
	CONSTRAINT scheduler_jobs_retry_count_check CHECK ((retry_count >= 0))
);
CREATE INDEX idx_scheduler_jobs_enabled ON public.scheduler_jobs USING btree (enabled);
CREATE INDEX idx_scheduler_jobs_next_run_at ON public.scheduler_jobs USING btree (next_run_at);
CREATE INDEX idx_scheduler_jobs_service_name ON public.scheduler_jobs USING btree (service_name);

-- Table Triggers

create trigger scheduler_jobs_set_updated_at before
update
    on
    public.scheduler_jobs for each row execute function set_updated_at();


-- public.sources definition

-- Drop table

-- DROP TABLE public.sources;

CREATE TABLE public.sources (
	id bigserial NOT NULL,
	source_type text NOT NULL,
	"name" text NOT NULL,
	base_url text NULL,
	"domain" text NULL,
	category text NOT NULL,
	is_active bool DEFAULT true NOT NULL,
	created_at timestamptz DEFAULT now() NOT NULL,
	updated_at timestamptz DEFAULT now() NOT NULL,
	CONSTRAINT sources_category_check CHECK ((category = ANY (ARRAY['stocks'::text, 'crypto'::text]))),
	CONSTRAINT sources_name_key UNIQUE (name),
	CONSTRAINT sources_pkey PRIMARY KEY (id),
	CONSTRAINT sources_source_type_non_empty CHECK ((length(TRIM(BOTH FROM source_type)) > 0))
);
CREATE INDEX idx_sources_category ON public.sources USING btree (category);
CREATE INDEX idx_sources_source_type ON public.sources USING btree (source_type);

-- Table Triggers

create trigger sources_set_updated_at before
update
    on
    public.sources for each row execute function set_updated_at();


-- public.ingestion_runs definition

-- Drop table

-- DROP TABLE public.ingestion_runs;

CREATE TABLE public.ingestion_runs (
	id bigserial NOT NULL,
	job_id int8 NULL,
	source_id int8 NULL,
	run_type text NOT NULL,
	status text NOT NULL,
	started_at timestamptz NOT NULL,
	finished_at timestamptz NULL,
	items_seen int4 DEFAULT 0 NOT NULL,
	items_inserted int4 DEFAULT 0 NOT NULL,
	items_updated int4 DEFAULT 0 NOT NULL,
	error_message text NULL,
	metadata jsonb NULL,
	created_at timestamptz DEFAULT now() NOT NULL,
	CONSTRAINT ingestion_runs_items_inserted_check CHECK ((items_inserted >= 0)),
	CONSTRAINT ingestion_runs_items_seen_check CHECK ((items_seen >= 0)),
	CONSTRAINT ingestion_runs_items_updated_check CHECK ((items_updated >= 0)),
	CONSTRAINT ingestion_runs_pkey PRIMARY KEY (id),
	CONSTRAINT ingestion_runs_job_id_fkey FOREIGN KEY (job_id) REFERENCES public.scheduler_jobs(id),
	CONSTRAINT ingestion_runs_source_id_fkey FOREIGN KEY (source_id) REFERENCES public.sources(id)
);
CREATE INDEX idx_ingestion_runs_job_id ON public.ingestion_runs USING btree (job_id);
CREATE INDEX idx_ingestion_runs_run_type ON public.ingestion_runs USING btree (run_type);
CREATE INDEX idx_ingestion_runs_source_id ON public.ingestion_runs USING btree (source_id);
CREATE INDEX idx_ingestion_runs_started_at ON public.ingestion_runs USING btree (started_at DESC);
CREATE INDEX idx_ingestion_runs_status ON public.ingestion_runs USING btree (status);


-- public.markets definition

-- Drop table

-- DROP TABLE public.markets;

CREATE TABLE public.markets (
	id bigserial NOT NULL,
	source_id int8 NULL,
	external_id text NOT NULL,
	slug text NULL,
	title text NOT NULL,
	description text NULL,
	category text NOT NULL,
	status text DEFAULT 'unknown'::text NULL,
	url text NULL,
	published_at timestamptz NULL,
	resolved_at timestamptz NULL,
	created_at timestamptz DEFAULT now() NOT NULL,
	updated_at timestamptz DEFAULT now() NOT NULL,
	"source" text DEFAULT 'polymarket'::text NOT NULL,
	score numeric DEFAULT 0 NOT NULL,
	metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
	CONSTRAINT markets_category_check CHECK ((category = ANY (ARRAY['stocks'::text, 'crypto'::text]))),
	CONSTRAINT markets_external_id_key UNIQUE (external_id),
	CONSTRAINT markets_pkey PRIMARY KEY (id),
	CONSTRAINT markets_source_external_unique UNIQUE (source_id, external_id),
	CONSTRAINT markets_source_id_key UNIQUE (source_id),
	CONSTRAINT markets_source_id_fkey FOREIGN KEY (source_id) REFERENCES public.sources(id)
);
CREATE INDEX idx_markets_category ON public.markets USING btree (category);
CREATE INDEX idx_markets_external_id ON public.markets USING btree (source_id, external_id);
CREATE INDEX idx_markets_published_at ON public.markets USING btree (published_at);
CREATE INDEX idx_markets_source_id ON public.markets USING btree (source_id);
CREATE INDEX idx_markets_status ON public.markets USING btree (status);

-- Table Triggers

create trigger markets_set_updated_at before
update
    on
    public.markets for each row execute function set_updated_at();


-- public.news_items definition

-- Drop table

-- DROP TABLE public.news_items;

CREATE TABLE public.news_items (
	id bigserial NOT NULL,
	source_id int8 NOT NULL,
	market_id int8 NULL,
	external_id text NULL,
	title text NOT NULL,
	summary text NULL,
	"content" text NULL,
	url text NOT NULL,
	"domain" text NULL,
	category text NOT NULL,
	published_at timestamptz NULL,
	fetched_at timestamptz DEFAULT now() NOT NULL,
	created_at timestamptz DEFAULT now() NOT NULL,
	CONSTRAINT news_items_category_check CHECK ((category = ANY (ARRAY['stocks'::text, 'crypto'::text]))),
	CONSTRAINT news_items_pkey PRIMARY KEY (id),
	CONSTRAINT news_items_source_external_unique UNIQUE (source_id, external_id),
	CONSTRAINT news_items_url_unique UNIQUE (url),
	CONSTRAINT news_items_market_id_fkey FOREIGN KEY (market_id) REFERENCES public.markets(id),
	CONSTRAINT news_items_source_id_fkey FOREIGN KEY (source_id) REFERENCES public.sources(id)
);
CREATE INDEX idx_news_items_category ON public.news_items USING btree (category);
CREATE INDEX idx_news_items_domain ON public.news_items USING btree (domain);
CREATE INDEX idx_news_items_market_id ON public.news_items USING btree (market_id);
CREATE INDEX idx_news_items_published_at ON public.news_items USING btree (published_at);
CREATE INDEX idx_news_items_source_id ON public.news_items USING btree (source_id);


-- public.research_reports definition

-- Drop table

-- DROP TABLE public.research_reports;

CREATE TABLE public.research_reports (
	id bigserial NOT NULL,
	title text NOT NULL,
	summary text NOT NULL,
	details text NULL,
	category text NOT NULL,
	market_id int8 NULL,
	source_window_start timestamptz NULL,
	source_window_end timestamptz NULL,
	status text NOT NULL,
	created_at timestamptz DEFAULT now() NOT NULL,
	updated_at timestamptz DEFAULT now() NOT NULL,
	CONSTRAINT research_reports_category_check CHECK ((category = ANY (ARRAY['stocks'::text, 'crypto'::text]))),
	CONSTRAINT research_reports_pkey PRIMARY KEY (id),
	CONSTRAINT research_reports_market_id_fkey FOREIGN KEY (market_id) REFERENCES public.markets(id)
);
CREATE INDEX idx_research_reports_category ON public.research_reports USING btree (category);
CREATE INDEX idx_research_reports_created_at ON public.research_reports USING btree (created_at DESC);
CREATE INDEX idx_research_reports_market_id ON public.research_reports USING btree (market_id);
CREATE INDEX idx_research_reports_status ON public.research_reports USING btree (status);

-- Table Triggers

create trigger research_reports_set_updated_at before
update
    on
    public.research_reports for each row execute function set_updated_at();


-- public.telegram_messages definition

-- Drop table

-- DROP TABLE public.telegram_messages;

CREATE TABLE public.telegram_messages (
	id bigserial NOT NULL,
	report_id int8 NULL,
	chat_id text NOT NULL,
	message_type text NOT NULL,
	title text NULL,
	body text NOT NULL,
	payload jsonb NULL,
	status text NOT NULL,
	scheduled_for timestamptz NULL,
	sent_at timestamptz NULL,
	attempt_count int4 DEFAULT 0 NOT NULL,
	last_error text NULL,
	created_at timestamptz DEFAULT now() NOT NULL,
	updated_at timestamptz DEFAULT now() NOT NULL,
	CONSTRAINT telegram_messages_attempt_count_check CHECK ((attempt_count >= 0)),
	CONSTRAINT telegram_messages_pkey PRIMARY KEY (id),
	CONSTRAINT telegram_messages_report_id_fkey FOREIGN KEY (report_id) REFERENCES public.research_reports(id)
);
CREATE INDEX idx_telegram_messages_chat_id ON public.telegram_messages USING btree (chat_id);
CREATE INDEX idx_telegram_messages_report_id ON public.telegram_messages USING btree (report_id);
CREATE INDEX idx_telegram_messages_scheduled_for ON public.telegram_messages USING btree (scheduled_for);
CREATE INDEX idx_telegram_messages_status ON public.telegram_messages USING btree (status);

-- Table Triggers

create trigger telegram_messages_set_updated_at before
update
    on
    public.telegram_messages for each row execute function set_updated_at();


-- public.market_snapshots definition

-- Drop table

-- DROP TABLE public.market_snapshots;

CREATE TABLE public.market_snapshots (
	id bigserial NOT NULL,
	market_id int8 NOT NULL,
	snapshot_time timestamptz NOT NULL,
	source_id int8 NOT NULL,
	price numeric(18, 8) NULL,
	best_bid numeric(18, 8) NULL,
	best_ask numeric(18, 8) NULL,
	volume_24h numeric(18, 8) NULL,
	liquidity numeric(18, 8) NULL,
	raw_payload jsonb NULL,
	created_at timestamptz DEFAULT now() NOT NULL,
	CONSTRAINT market_snapshots_pkey PRIMARY KEY (id),
	CONSTRAINT market_snapshots_market_id_fkey FOREIGN KEY (market_id) REFERENCES public.markets(id),
	CONSTRAINT market_snapshots_source_id_fkey FOREIGN KEY (source_id) REFERENCES public.sources(id)
);
CREATE INDEX idx_market_snapshots_market_id ON public.market_snapshots USING btree (market_id);
CREATE INDEX idx_market_snapshots_market_time ON public.market_snapshots USING btree (market_id, snapshot_time DESC);
CREATE INDEX idx_market_snapshots_snapshot_time ON public.market_snapshots USING btree (snapshot_time DESC);
CREATE INDEX idx_market_snapshots_source_id ON public.market_snapshots USING btree (source_id);