-- This Is The Starting Point Of Migrations


--
-- PostgreSQL database dump
--

-- Dumped from database version 16.9 (Ubuntu 16.9-0ubuntu0.24.10.1)
-- Dumped by pg_dump version 17.5

-- Started on 2025-07-15 17:14:55

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- TOC entry 6 (class 2615 OID 16392)
-- Name: surveys; Type: SCHEMA; Schema: -; Owner: wolfy
--

CREATE SCHEMA surveys;


ALTER SCHEMA surveys OWNER TO wolfy;

--
-- TOC entry 227 (class 1255 OID 16473)
-- Name: enforce_question_data_constraints(); Type: FUNCTION; Schema: surveys; Owner: wolfy
--

CREATE FUNCTION surveys.enforce_question_data_constraints() RETURNS trigger
    LANGUAGE plpgsql
    AS $$DECLARE
	_elem JSONB;
BEGIN
    IF NEW.type = 0 THEN
        -- Check that 'min_length' and 'max_length' exist and are integers
        IF NOT (NEW.question_data ? 'min_length' AND jsonb_typeof(NEW.question_data->'min_length') = 'number') THEN
            RAISE EXCEPTION 'min_length Must Be An Integer For Text Questions';
        END IF;
        IF NOT (NEW.question_data ? 'max_length' AND jsonb_typeof(NEW.question_data->'max_length') = 'number') THEN
            RAISE EXCEPTION 'max_length Must Be An Integer For Text Questions';
        END IF;
	ELSIF NEW.type = 1 THEN
		-- Check that 'min_selects' and 'max_selects' exist and are integers
		IF NOT (NEW.question_data ? 'min_selects' AND jsonb_typeof(NEW.question_data->'min_selects') = 'number') THEN
            RAISE EXCEPTION 'min_selects Must Be An Integer For Multiple Choice Questions';
        END IF;
        IF NOT (NEW.question_data ? 'max_selects' AND jsonb_typeof(NEW.question_data->'max_selects') = 'number') THEN
            RAISE EXCEPTION 'max_selects Must Be An Integer For Multiple Choice Questions';
        END IF;
		-- Check if 'options' is a list of json
		IF NOT (NEW.question_data ? 'options' AND jsonb_typeof(NEW.question_data->'options') = 'array') THEN
            RAISE EXCEPTION 'options Must Be An Array For Multiple Choice Questions';
        END IF;
		-- Check if every item in 'options' is valid
		FOR _elem IN (SELECT jsonb_array_elements FROM jsonb_array_elements(NEW.question_data->'options'))
		LOOP
			-- Check if 'text' exists and is a string
			IF NOT (_elem ? 'text' AND jsonb_typeof(_elem->'text') = 'string') THEN
	            RAISE EXCEPTION 'text Must Be An String For Options Of Multiple Choice Questions';
	        END IF;
			-- Check if 'id' exists and is a integer
			IF NOT (_elem ? 'id' AND jsonb_typeof(_elem->'id') = 'number') THEN
	            RAISE EXCEPTION 'id Must Be An Integer For Options Of Multiple Choice Questions';
	        END IF;
		END LOOP;
	ELSIF NEW.type = 2 THEN
		-- Check that 'type' exists and is an integer
		IF NOT (NEW.question_data ? 'type' AND jsonb_typeof(NEW.question_data->'type') = 'number') THEN
            RAISE EXCEPTION 'type Must Be An Integer For DateTime Questions';
        END IF;
		-- Check if 'minimum' and 'maximum' exist
		IF NOT (NEW.question_data ? 'minimum' AND jsonb_typeof(NEW.question_data->'minimum') = 'string') THEN
            RAISE EXCEPTION 'minimum Must Be A String For DateTime Questions';
        END IF;
		IF NOT (NEW.question_data ? 'maximum' AND jsonb_typeof(NEW.question_data->'maximum') = 'string') THEN
            RAISE EXCEPTION 'maximum Must Be A String For DateTime Questions';
        END IF;
    ELSE
		RAISE EXCEPTION 'Unknown Question Type';
	END IF;
    RETURN NEW;
END;$$;


ALTER FUNCTION surveys.enforce_question_data_constraints() OWNER TO wolfy;

--
-- TOC entry 239 (class 1255 OID 16474)
-- Name: enforce_response_data_constraints(); Type: FUNCTION; Schema: surveys; Owner: wolfy
--

CREATE FUNCTION surveys.enforce_response_data_constraints() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
	qtype integer;
	_elem JSONB;
BEGIN
	SELECT questions.type INTO qtype FROM surveys.questions WHERE questions.id=NEW.question;
    IF qtype = 0 THEN
        IF NOT (NEW.response_data ? 'text' AND jsonb_typeof(NEW.response_data->'text') = 'string') THEN
            RAISE EXCEPTION 'text Must Be A String For Text Questions';
        END IF;
	ELSIF qtype = 1 THEN
		IF NOT (NEW.response_data ? 'selected' AND jsonb_typeof(NEW.response_data->'selected') = 'array') THEN
            RAISE EXCEPTION 'selected Must Be A Array For Multiple Choice Questions';
        END IF;
		-- Check if it is an array of integers
		FOR _elem IN SELECT jsonb_array_elements FROM jsonb_array_elements(NEW.response_data->'options')
        LOOP
            -- Check if every element is a number
            IF NOT (jsonb_typeof(_elem) = 'number') THEN
                RAISE EXCEPTION 'Elements Of selected Must Be A Integer For Multiple Choice Questions';
            END IF;
        END LOOP;
	ELSIF qtype = 2 THEN
		IF NOT (NEW.response_data ? 'timestamp' AND jsonb_typeof(NEW.response_data->'timestamp') = 'string') THEN
            RAISE EXCEPTION 'timestamp Must Be A String For DateTime Questions';
        END IF;
    ELSE
		RAISE EXCEPTION 'Unknown Question Type';
	END IF;
    RETURN NEW;
END;
$$;


ALTER FUNCTION surveys.enforce_response_data_constraints() OWNER TO wolfy;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- TOC entry 216 (class 1259 OID 16395)
-- Name: active_guild_surveys; Type: TABLE; Schema: surveys; Owner: wolfy
--

CREATE TABLE surveys.active_guild_surveys (
    id integer NOT NULL,
    end_date timestamp without time zone NOT NULL,
    template_id integer NOT NULL,
    channel_id integer,
    message_id integer
);


ALTER TABLE surveys.active_guild_surveys OWNER TO wolfy;

--
-- TOC entry 217 (class 1259 OID 16398)
-- Name: active_guild_surveys_id_seq; Type: SEQUENCE; Schema: surveys; Owner: wolfy
--

ALTER TABLE surveys.active_guild_surveys ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME surveys.active_guild_surveys_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 226 (class 1259 OID 16502)
-- Name: data_sharing_consent; Type: TABLE; Schema: surveys; Owner: survey_wolf_bot
--

CREATE TABLE surveys.data_sharing_consent (
    user_id character varying NOT NULL,
    guild_id character varying NOT NULL,
    "timestamp" timestamp without time zone NOT NULL,
    version_id smallint
);


ALTER TABLE surveys.data_sharing_consent OWNER TO survey_wolf_bot;

--
-- TOC entry 218 (class 1259 OID 16399)
-- Name: template; Type: TABLE; Schema: surveys; Owner: wolfy
--

CREATE TABLE surveys.template (
    id integer NOT NULL,
    guild_id bigint NOT NULL,
    anonymous smallint NOT NULL,
    editable boolean DEFAULT false,
    entries_per integer DEFAULT 1 NOT NULL,
    max_entries integer,
    time_limit interval(0),
    title character varying(64) NOT NULL,
    description character varying
);


ALTER TABLE surveys.template OWNER TO wolfy;

--
-- TOC entry 219 (class 1259 OID 16406)
-- Name: guild_surveys_id_seq; Type: SEQUENCE; Schema: surveys; Owner: wolfy
--

CREATE SEQUENCE surveys.guild_surveys_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE surveys.guild_surveys_id_seq OWNER TO wolfy;

--
-- TOC entry 3461 (class 0 OID 0)
-- Dependencies: 219
-- Name: guild_surveys_id_seq; Type: SEQUENCE OWNED BY; Schema: surveys; Owner: wolfy
--

ALTER SEQUENCE surveys.guild_surveys_id_seq OWNED BY surveys.template.id;


--
-- TOC entry 220 (class 1259 OID 16407)
-- Name: question_response; Type: TABLE; Schema: surveys; Owner: wolfy
--

CREATE TABLE surveys.question_response (
    id integer NOT NULL,
    question integer NOT NULL,
    response_data jsonb,
    response integer NOT NULL
);


ALTER TABLE surveys.question_response OWNER TO wolfy;

--
-- TOC entry 221 (class 1259 OID 16412)
-- Name: question_response_id_seq; Type: SEQUENCE; Schema: surveys; Owner: wolfy
--

ALTER TABLE surveys.question_response ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME surveys.question_response_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 222 (class 1259 OID 16413)
-- Name: questions; Type: TABLE; Schema: surveys; Owner: wolfy
--

CREATE TABLE surveys.questions (
    text character varying NOT NULL,
    id integer NOT NULL,
    "position" integer,
    survey_id integer NOT NULL,
    required boolean DEFAULT false NOT NULL,
    description character varying,
    type smallint DEFAULT 0 NOT NULL,
    question_data jsonb
);


ALTER TABLE surveys.questions OWNER TO wolfy;

--
-- TOC entry 3465 (class 0 OID 0)
-- Dependencies: 222
-- Name: COLUMN questions.question_data; Type: COMMENT; Schema: surveys; Owner: wolfy
--

COMMENT ON COLUMN surveys.questions.question_data IS 'This Is Any Information The Is Specific To The Question Type';


--
-- TOC entry 223 (class 1259 OID 16420)
-- Name: questions_id_seq; Type: SEQUENCE; Schema: surveys; Owner: wolfy
--

CREATE SEQUENCE surveys.questions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE surveys.questions_id_seq OWNER TO wolfy;

--
-- TOC entry 3467 (class 0 OID 0)
-- Dependencies: 223
-- Name: questions_id_seq; Type: SEQUENCE OWNED BY; Schema: surveys; Owner: wolfy
--

ALTER SEQUENCE surveys.questions_id_seq OWNED BY surveys.questions.id;


--
-- TOC entry 224 (class 1259 OID 16421)
-- Name: responses; Type: TABLE; Schema: surveys; Owner: wolfy
--

CREATE TABLE surveys.responses (
    user_id character varying NOT NULL,
    id integer NOT NULL,
    response_num integer NOT NULL,
    active_survey_id integer NOT NULL,
    template_id integer NOT NULL
);


ALTER TABLE surveys.responses OWNER TO wolfy;

--
-- TOC entry 3469 (class 0 OID 0)
-- Dependencies: 224
-- Name: COLUMN responses.user_id; Type: COMMENT; Schema: surveys; Owner: wolfy
--

COMMENT ON COLUMN surveys.responses.user_id IS 'This is an encrypted version of the User ID';


--
-- TOC entry 225 (class 1259 OID 16426)
-- Name: responses_id_seq; Type: SEQUENCE; Schema: surveys; Owner: wolfy
--

ALTER TABLE surveys.responses ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME surveys.responses_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 3281 (class 2604 OID 16475)
-- Name: questions id; Type: DEFAULT; Schema: surveys; Owner: wolfy
--

ALTER TABLE ONLY surveys.questions ALTER COLUMN id SET DEFAULT nextval('surveys.questions_id_seq'::regclass);


--
-- TOC entry 3278 (class 2604 OID 16476)
-- Name: template id; Type: DEFAULT; Schema: surveys; Owner: wolfy
--

ALTER TABLE ONLY surveys.template ALTER COLUMN id SET DEFAULT nextval('surveys.guild_surveys_id_seq'::regclass);


--
-- TOC entry 3286 (class 2606 OID 16430)
-- Name: active_guild_surveys active_guild_surveys_pk; Type: CONSTRAINT; Schema: surveys; Owner: wolfy
--

ALTER TABLE ONLY surveys.active_guild_surveys
    ADD CONSTRAINT active_guild_surveys_pk PRIMARY KEY (id);


--
-- TOC entry 3299 (class 2606 OID 16508)
-- Name: data_sharing_consent data_sharing_consent_pkey; Type: CONSTRAINT; Schema: surveys; Owner: survey_wolf_bot
--

ALTER TABLE ONLY surveys.data_sharing_consent
    ADD CONSTRAINT data_sharing_consent_pkey PRIMARY KEY (user_id, guild_id);


--
-- TOC entry 3289 (class 2606 OID 16432)
-- Name: template guild_surveys_pk; Type: CONSTRAINT; Schema: surveys; Owner: wolfy
--

ALTER TABLE ONLY surveys.template
    ADD CONSTRAINT guild_surveys_pk PRIMARY KEY (id);


--
-- TOC entry 3291 (class 2606 OID 16434)
-- Name: question_response question_response_pk; Type: CONSTRAINT; Schema: surveys; Owner: wolfy
--

ALTER TABLE ONLY surveys.question_response
    ADD CONSTRAINT question_response_pk PRIMARY KEY (id);


--
-- TOC entry 3294 (class 2606 OID 16436)
-- Name: questions questions_pk; Type: CONSTRAINT; Schema: surveys; Owner: wolfy
--

ALTER TABLE ONLY surveys.questions
    ADD CONSTRAINT questions_pk PRIMARY KEY (id);


--
-- TOC entry 3297 (class 2606 OID 16438)
-- Name: responses responses_pkey; Type: CONSTRAINT; Schema: surveys; Owner: wolfy
--

ALTER TABLE ONLY surveys.responses
    ADD CONSTRAINT responses_pkey PRIMARY KEY (id);


--
-- TOC entry 3284 (class 1259 OID 16439)
-- Name: active_guild_surveys_id_uindex; Type: INDEX; Schema: surveys; Owner: wolfy
--

CREATE UNIQUE INDEX active_guild_surveys_id_uindex ON surveys.active_guild_surveys USING btree (id);


--
-- TOC entry 3295 (class 1259 OID 16440)
-- Name: fki_active_survey_fk; Type: INDEX; Schema: surveys; Owner: wolfy
--

CREATE INDEX fki_active_survey_fk ON surveys.responses USING btree (active_survey_id);


--
-- TOC entry 3287 (class 1259 OID 16441)
-- Name: guild_surveys_id_uindex; Type: INDEX; Schema: surveys; Owner: wolfy
--

CREATE UNIQUE INDEX guild_surveys_id_uindex ON surveys.template USING btree (id);


--
-- TOC entry 3292 (class 1259 OID 16442)
-- Name: questions_id_uindex; Type: INDEX; Schema: surveys; Owner: wolfy
--

CREATE UNIQUE INDEX questions_id_uindex ON surveys.questions USING btree (id);


--
-- TOC entry 3307 (class 2620 OID 16477)
-- Name: questions validate_question_data; Type: TRIGGER; Schema: surveys; Owner: wolfy
--

CREATE TRIGGER validate_question_data BEFORE INSERT OR UPDATE ON surveys.questions FOR EACH ROW EXECUTE FUNCTION surveys.enforce_question_data_constraints();


--
-- TOC entry 3306 (class 2620 OID 16478)
-- Name: question_response validate_response_data; Type: TRIGGER; Schema: surveys; Owner: wolfy
--

CREATE TRIGGER validate_response_data BEFORE INSERT OR UPDATE ON surveys.question_response FOR EACH ROW EXECUTE FUNCTION surveys.enforce_response_data_constraints();


--
-- TOC entry 3300 (class 2606 OID 16443)
-- Name: active_guild_surveys active_guild_surveys_guild_surveys_id_fk; Type: FK CONSTRAINT; Schema: surveys; Owner: wolfy
--

ALTER TABLE ONLY surveys.active_guild_surveys
    ADD CONSTRAINT active_guild_surveys_guild_surveys_id_fk FOREIGN KEY (template_id) REFERENCES surveys.template(id) ON DELETE CASCADE;


--
-- TOC entry 3304 (class 2606 OID 16448)
-- Name: responses active_survey_fk; Type: FK CONSTRAINT; Schema: surveys; Owner: wolfy
--

ALTER TABLE ONLY surveys.responses
    ADD CONSTRAINT active_survey_fk FOREIGN KEY (active_survey_id) REFERENCES surveys.active_guild_surveys(id) ON DELETE CASCADE;


--
-- TOC entry 3301 (class 2606 OID 16489)
-- Name: question_response question_response_questions_id_fk; Type: FK CONSTRAINT; Schema: surveys; Owner: wolfy
--

ALTER TABLE ONLY surveys.question_response
    ADD CONSTRAINT question_response_questions_id_fk FOREIGN KEY (question) REFERENCES surveys.questions(id) ON DELETE CASCADE;


--
-- TOC entry 3302 (class 2606 OID 16458)
-- Name: question_response question_response_responses_id_fk; Type: FK CONSTRAINT; Schema: surveys; Owner: wolfy
--

ALTER TABLE ONLY surveys.question_response
    ADD CONSTRAINT question_response_responses_id_fk FOREIGN KEY (response) REFERENCES surveys.responses(id);


--
-- TOC entry 3303 (class 2606 OID 16463)
-- Name: questions survey_fk; Type: FK CONSTRAINT; Schema: surveys; Owner: wolfy
--

ALTER TABLE ONLY surveys.questions
    ADD CONSTRAINT survey_fk FOREIGN KEY (survey_id) REFERENCES surveys.template(id) ON DELETE CASCADE;


--
-- TOC entry 3305 (class 2606 OID 16484)
-- Name: responses template___fk; Type: FK CONSTRAINT; Schema: surveys; Owner: wolfy
--

ALTER TABLE ONLY surveys.responses
    ADD CONSTRAINT template___fk FOREIGN KEY (template_id) REFERENCES surveys.template(id) ON DELETE CASCADE;


--
-- TOC entry 3457 (class 0 OID 0)
-- Dependencies: 6
-- Name: SCHEMA surveys; Type: ACL; Schema: -; Owner: wolfy
--

GRANT USAGE ON SCHEMA surveys TO survey_wolf_bot;


--
-- TOC entry 3458 (class 0 OID 0)
-- Dependencies: 216
-- Name: TABLE active_guild_surveys; Type: ACL; Schema: surveys; Owner: wolfy
--

GRANT SELECT,INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,UPDATE ON TABLE surveys.active_guild_surveys TO survey_wolf_bot;


--
-- TOC entry 3459 (class 0 OID 0)
-- Dependencies: 217
-- Name: SEQUENCE active_guild_surveys_id_seq; Type: ACL; Schema: surveys; Owner: wolfy
--

GRANT ALL ON SEQUENCE surveys.active_guild_surveys_id_seq TO survey_wolf_bot;


--
-- TOC entry 3460 (class 0 OID 0)
-- Dependencies: 218
-- Name: TABLE template; Type: ACL; Schema: surveys; Owner: wolfy
--

GRANT SELECT,INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,UPDATE ON TABLE surveys.template TO survey_wolf_bot;


--
-- TOC entry 3462 (class 0 OID 0)
-- Dependencies: 219
-- Name: SEQUENCE guild_surveys_id_seq; Type: ACL; Schema: surveys; Owner: wolfy
--

GRANT ALL ON SEQUENCE surveys.guild_surveys_id_seq TO survey_wolf_bot;


--
-- TOC entry 3463 (class 0 OID 0)
-- Dependencies: 220
-- Name: TABLE question_response; Type: ACL; Schema: surveys; Owner: wolfy
--

GRANT SELECT,INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,UPDATE ON TABLE surveys.question_response TO survey_wolf_bot;


--
-- TOC entry 3464 (class 0 OID 0)
-- Dependencies: 221
-- Name: SEQUENCE question_response_id_seq; Type: ACL; Schema: surveys; Owner: wolfy
--

GRANT ALL ON SEQUENCE surveys.question_response_id_seq TO survey_wolf_bot;


--
-- TOC entry 3466 (class 0 OID 0)
-- Dependencies: 222
-- Name: TABLE questions; Type: ACL; Schema: surveys; Owner: wolfy
--

GRANT SELECT,INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,UPDATE ON TABLE surveys.questions TO survey_wolf_bot;


--
-- TOC entry 3468 (class 0 OID 0)
-- Dependencies: 223
-- Name: SEQUENCE questions_id_seq; Type: ACL; Schema: surveys; Owner: wolfy
--

GRANT ALL ON SEQUENCE surveys.questions_id_seq TO survey_wolf_bot;


--
-- TOC entry 3470 (class 0 OID 0)
-- Dependencies: 224
-- Name: TABLE responses; Type: ACL; Schema: surveys; Owner: wolfy
--

GRANT SELECT,INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,UPDATE ON TABLE surveys.responses TO survey_wolf_bot;


--
-- TOC entry 3471 (class 0 OID 0)
-- Dependencies: 225
-- Name: SEQUENCE responses_id_seq; Type: ACL; Schema: surveys; Owner: wolfy
--

GRANT ALL ON SEQUENCE surveys.responses_id_seq TO survey_wolf_bot;


--
-- TOC entry 2066 (class 826 OID 16394)
-- Name: DEFAULT PRIVILEGES FOR SEQUENCES; Type: DEFAULT ACL; Schema: surveys; Owner: wolfy
--

ALTER DEFAULT PRIVILEGES FOR ROLE wolfy IN SCHEMA surveys GRANT ALL ON SEQUENCES TO survey_wolf_bot;


--
-- TOC entry 2065 (class 826 OID 16393)
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: surveys; Owner: wolfy
--

ALTER DEFAULT PRIVILEGES FOR ROLE wolfy IN SCHEMA surveys GRANT SELECT,INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,UPDATE ON TABLES TO survey_wolf_bot;


-- Completed on 2025-07-15 17:14:59

--
-- PostgreSQL database dump complete
--

