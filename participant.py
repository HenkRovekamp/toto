import os
import streamlit as st
from dotenv import load_dotenv
from src.db import (
    init_fantasy_tables, init_accounts_table,
    save_fantasy_team, load_team_by_account,
    get_account_by_email, create_account,
    _connect, load_races, is_registration_open,
)

load_dotenv()

_TOKEN = os.getenv("MOTHERDUCK_TOKEN") or st.secrets.get("MOTHERDUCK_TOKEN", "")
if _TOKEN:
    DB_PATH = f"md:toto?motherduck_token={_TOKEN}"
else:
    DB_PATH = os.path.join(os.path.dirname(__file__), "data", "cycling.duckdb")

st.set_page_config(page_title="Stampers Toto", page_icon="🚴", layout="centered")
st.title("🚴 Stampers Toto")

if not DB_PATH.startswith("md:") and not os.path.exists(DB_PATH):
    st.error("Database not found. Ask the administrator to run the scraper first.")
    st.stop()

init_fantasy_tables(DB_PATH)
init_accounts_table(DB_PATH)

# ── Session state ─────────────────────────────────────────────────────────────
if "account" not in st.session_state:
    st.session_state.account = None

# ── Account login / registration ──────────────────────────────────────────────
if st.session_state.account is None:
    st.subheader("Inloggen / registreren")

    email_input = st.text_input("E-mailadres", placeholder="e.g. johan@example.com")

    if not email_input.strip():
        st.stop()

    account = get_account_by_email(DB_PATH, email_input.strip())

    if account:
        st.success(f"Welkom terug, **{account['name']}**!")
        if st.button("Doorgaan", use_container_width=True):
            st.session_state.account = account
            st.rerun()
    else:
        st.info("Nog geen account. Voer je naam in om je te registreren.")
        name_input = st.text_input("Jouw naam", placeholder="e.g. Johan")
        if name_input.strip():
            if st.button("Account aanmaken", use_container_width=True):
                account = create_account(DB_PATH, email_input.strip(), name_input.strip())
                st.session_state.account = account
                st.rerun()

    st.stop()

# ── Logged in ─────────────────────────────────────────────────────────────────
account = st.session_state.account

col_welcome, col_logout = st.columns([4, 1])
col_welcome.markdown(f"Ingelogd als **{account['name']}** ({account['email']})")
if col_logout.button("Uitloggen"):
    st.session_state.account = None
    st.rerun()

st.divider()

# ── Race selection ────────────────────────────────────────────────────────────
races = load_races(DB_PATH)
if not races:
    st.error("No races configured yet. Ask the administrator.")
    st.stop()

race_options = {r["race_name"]: r for r in races}
selected_race = st.selectbox("Selecteer een race", list(race_options.keys()))

race_info = race_options[selected_race]
registration_open = is_registration_open(DB_PATH, selected_race)

if race_info["deadline"]:
    if registration_open:
        st.info(f"⏰ Inschrijving sluit op **{race_info['deadline'].strftime('%d/%m/%Y om %H:%M')}**")
    else:
        st.error(f"⏰ Inschrijving gesloten op **{race_info['deadline'].strftime('%d/%m/%Y om %H:%M')}**. Geen nieuwe teams mogelijk.")

# ── Load all riders ───────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def get_rider_options():
    conn = _connect(DB_PATH, read_only=True)
    try:
        df = conn.execute(
            "SELECT rider_url, name, nationality, team_name FROM riders WHERE name IS NOT NULL ORDER BY name"
        ).df()
    finally:
        conn.close()
    return {
        f"{row['name']} ({row['nationality'] or '?'}) — {row['team_name'] or '?'}": row["rider_url"]
        for _, row in df.iterrows()
    }

rider_options = get_rider_options()

# ── Team form ─────────────────────────────────────────────────────────────────
if not registration_open:
    st.stop()

existing_team = load_team_by_account(DB_PATH, account["id"], selected_race)

url_to_label = {v: k for k, v in rider_options.items()}
prefill_labels = [url_to_label[u] for u in (existing_team["rider_urls"] if existing_team else []) if u in url_to_label]
prefill_team_name = existing_team["team_name"] if existing_team else ""

if existing_team:
    st.info(f"✏️ Je hebt al een team voor deze race: **{prefill_team_name}**. Opslaan overschrijft je bestaande selectie.")

with st.form("participant_form"):
    team_name = st.text_input("Teamnaam", value=prefill_team_name, placeholder="e.g. Team Velodutch")

    selected_labels = st.multiselect(
        "Selecteer renners (max 15)",
        options=list(rider_options.keys()),
        default=prefill_labels,
        max_selections=15,
        placeholder="Type een naam om te zoeken...",
    )

    st.caption(f"{len(selected_labels)} / 15 renners geselecteerd")
    submitted = st.form_submit_button("✅ Team opslaan", use_container_width=True)

if submitted:
    errors = []
    if not team_name.strip():
        errors.append("Voer een teamnaam in.")
    if len(selected_labels) == 0:
        errors.append("Selecteer minimaal 1 renner.")
    if not is_registration_open(DB_PATH, selected_race):
        errors.append("Inschrijving is gesloten voor deze race.")

    if errors:
        for e in errors:
            st.error(e)
    else:
        urls = [rider_options[lbl] for lbl in selected_labels]
        try:
            save_fantasy_team(
                DB_PATH,
                manager_name=account["name"],
                team_name=team_name.strip(),
                rider_urls=urls,
                race_name=selected_race,
                account_id=account["id"],
            )
            if existing_team:
                st.success(f"Team **{team_name.strip()}** bijgewerkt! 🎉")
            else:
                st.success(f"Team **{team_name.strip()}** geregistreerd! 🎉")
            st.balloons()
        except Exception as exc:
            st.error(f"Kon team niet opslaan: {exc}")
