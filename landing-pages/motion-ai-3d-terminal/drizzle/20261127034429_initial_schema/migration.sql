CREATE TABLE "agent_events" (
	"id" serial PRIMARY KEY NOT NULL,
	"agent_id" integer NOT NULL,
	"kind" text NOT NULL,
	"message" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "agents" (
	"id" serial PRIMARY KEY NOT NULL,
	"codename" text NOT NULL,
	"callsign" text NOT NULL,
	"role" text NOT NULL,
	"focus" text NOT NULL,
	"model" text NOT NULL,
	"status" text DEFAULT 'active' NOT NULL,
	"accuracy" double precision DEFAULT 60 NOT NULL,
	"pnl" double precision DEFAULT 0 NOT NULL,
	"signals_count" integer DEFAULT 0 NOT NULL,
	"latency_ms" integer DEFAULT 120 NOT NULL,
	"hue" integer DEFAULT 42 NOT NULL,
	"specialty" text NOT NULL,
	"generation" integer DEFAULT 1 NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "candles" (
	"id" serial PRIMARY KEY NOT NULL,
	"instrument_id" integer NOT NULL,
	"price" double precision NOT NULL,
	"volume" integer DEFAULT 0 NOT NULL,
	"ts" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "instruments" (
	"id" serial PRIMARY KEY NOT NULL,
	"symbol" text NOT NULL,
	"name" text NOT NULL,
	"market" text NOT NULL,
	"kind" text NOT NULL,
	"currency" text NOT NULL,
	"unit" text NOT NULL,
	"decimals" integer DEFAULT 2 NOT NULL,
	"price" double precision NOT NULL,
	"prev_close" double precision NOT NULL,
	"day_open" double precision NOT NULL,
	"day_high" double precision NOT NULL,
	"day_low" double precision NOT NULL,
	"volume" bigint DEFAULT 0 NOT NULL,
	"volatility" double precision DEFAULT 0.0006 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "signals" (
	"id" serial PRIMARY KEY NOT NULL,
	"agent_id" integer NOT NULL,
	"symbol" text NOT NULL,
	"market" text NOT NULL,
	"direction" text NOT NULL,
	"confidence" integer NOT NULL,
	"timeframe" text NOT NULL,
	"rationale" text NOT NULL,
	"entry" double precision NOT NULL,
	"target" double precision NOT NULL,
	"stop" double precision NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE INDEX "agent_events_created_idx" ON "agent_events" USING btree ("created_at");--> statement-breakpoint
CREATE UNIQUE INDEX "agents_codename_uidx" ON "agents" USING btree ("codename");--> statement-breakpoint
CREATE INDEX "agents_focus_idx" ON "agents" USING btree ("focus");--> statement-breakpoint
CREATE INDEX "candles_instrument_ts_idx" ON "candles" USING btree ("instrument_id","ts");--> statement-breakpoint
CREATE UNIQUE INDEX "instruments_symbol_uidx" ON "instruments" USING btree ("symbol");--> statement-breakpoint
CREATE INDEX "signals_created_idx" ON "signals" USING btree ("created_at");