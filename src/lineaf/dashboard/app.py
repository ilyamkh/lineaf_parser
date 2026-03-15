"""Lineaf — Streamlit dashboard for competitor price monitoring."""

from __future__ import annotations

import os
import re
from datetime import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Lineaf — Мониторинг цен",
    layout="wide",
    initial_sidebar_state="expanded",
)

API_BASE = os.environ.get("API_BASE_URL", "http://localhost:8000/api")

SITE_NAMES: dict[str, str] = {
    "askona": "Аскона",
    "ormatek": "Орматек",
    "sonum": "Сонум",
}

SITE_COLORS: dict[str, str] = {
    "Аскона": "#EF4444",
    "Орматек": "#F59E0B",
    "Сонум": "#3B82F6",
}

SITE_BG_COLORS: dict[str, str] = {
    "Аскона": "#FEF2F2",
    "Орматек": "#FFFBEB",
    "Сонум": "#EFF6FF",
}

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', -apple-system, sans-serif; }

    /* Fix header cutoff */
    .block-container { padding-top: 0.75rem !important; padding-bottom: 1rem; max-width: 1400px; }
    header[data-testid="stHeader"] { display: none !important; }

    /* Sidebar */
    section[data-testid="stSidebar"] { background: #F8FAFC; border-right: 1px solid #E2E8F0; }
    section[data-testid="stSidebar"] .stRadio [role="radiogroup"] { gap: 2px; }

    /* Tables: allow text wrapping */
    .stDataFrame td { white-space: normal !important; word-wrap: break-word !important; }
    .stDataFrame th { white-space: normal !important; }
    .stDataFrame { border-radius: 8px; }

    /* Compact subheaders */
    h3 { color: #1E293B; font-weight: 600; font-size: 1.05rem !important; margin-top: 0.25rem !important; }
    hr { margin: 0.5rem 0; border-color: #E2E8F0; }

    /* Buttons */
    .stButton button { border-radius: 8px; font-weight: 500; }

    /* Selectbox compact */
    .stSelectbox, .stMultiSelect { font-size: 0.9rem; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Cached API helpers
# ---------------------------------------------------------------------------


@st.cache_data(ttl=60)
def fetch_prices() -> list[dict]:
    return requests.get(f"{API_BASE}/prices", timeout=30).json()


@st.cache_data(ttl=60)
def fetch_product_details() -> list[dict]:
    return requests.get(f"{API_BASE}/products/details", timeout=30).json()


@st.cache_data(ttl=60)
def fetch_price_history(product_id: int) -> list[dict]:
    return requests.get(f"{API_BASE}/prices/history", params={"product_id": product_id}, timeout=30).json()


@st.cache_data(ttl=60)
def fetch_price_index() -> list[dict]:
    return requests.get(f"{API_BASE}/prices/index", timeout=30).json()


@st.cache_data(ttl=60)
def fetch_runs() -> list[dict]:
    return requests.get(f"{API_BASE}/runs", params={"limit": 50}, timeout=30).json()


@st.cache_data(ttl=60)
def fetch_freshness() -> list[dict]:
    return requests.get(f"{API_BASE}/runs/freshness", timeout=30).json()


@st.cache_data(ttl=60)
def fetch_changes() -> dict:
    return requests.get(f"{API_BASE}/products/changes", timeout=30).json()


def strip_html(val):
    return re.sub(r"<[^>]+>", "", val).strip() if val else val


def fmt_date(iso_str):
    if not iso_str:
        return "—"
    try:
        return datetime.fromisoformat(iso_str).strftime("%d.%m %H:%M")
    except (ValueError, TypeError):
        return "—"


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown(
        '<div style="font-size:1.4rem;font-weight:700;color:#1E40AF;padding:4px 0 2px;">Lineaf</div>',
        unsafe_allow_html=True,
    )
    st.caption("Мониторинг цен конкурентов")
    st.divider()

    page = st.radio(
        "Навигация",
        ["Каталог", "Графики", "Изменения", "Логи"],
        label_visibility="collapsed",
    )

    st.divider()
    st.markdown("**Фильтр конкурентов**")
    selected_sites: list[str] = st.multiselect(
        "Конкурент",
        options=list(SITE_NAMES.keys()),
        default=list(SITE_NAMES.keys()),
        format_func=lambda s: SITE_NAMES.get(s, s),
        label_visibility="collapsed",
    )

if not selected_sites:
    st.warning("Выберите хотя бы одного конкурента.")
    st.stop()

# ---------------------------------------------------------------------------
# Header: KPI cards (средняя цена + кол-во позиций + свежесть)
# ---------------------------------------------------------------------------

try:
    freshness_data = fetch_freshness()
    index_data = fetch_price_index()
    all_prices = fetch_prices()
except requests.exceptions.ConnectionError:
    st.error("Не удалось подключиться к API. Запустите сервер: `uvicorn lineaf.main:app`")
    st.stop()

# Count products per site
df_all_prices = pd.DataFrame(all_prices) if all_prices else pd.DataFrame()
site_counts = {}
if not df_all_prices.empty:
    site_counts = df_all_prices.groupby("source_site").size().to_dict()

index_map = {item["site"]: item.get("avg_price_sale", 0) for item in (index_data or [])}
fresh_map = {item["site"]: item for item in (freshness_data or [])}

st.markdown(
    '<div style="font-size:0.7rem;color:#94A3B8;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:6px;">'
    'Средняя цена со скидкой по конкурентам</div>',
    unsafe_allow_html=True,
)

cols = st.columns(len(SITE_NAMES))
for col, (site_key, site_name) in zip(cols, SITE_NAMES.items()):
    fresh = fresh_map.get(site_key, {})
    is_stale = fresh.get("is_stale", True)
    last_success = fresh.get("last_success")
    avg_price = index_map.get(site_key, 0)
    count = site_counts.get(site_key, 0)
    date_str = fmt_date(last_success)

    dot_color = "#22C55E" if not is_stale else "#EF4444"
    bg = SITE_BG_COLORS.get(site_name, "#F8FAFC")
    border = SITE_COLORS.get(site_name, "#3B82F6")

    with col:
        st.markdown(
            f'<div style="background:{bg};border:1px solid #E2E8F0;border-left:4px solid {border};'
            f'border-radius:8px;padding:10px 14px;margin-bottom:4px;">'
            f'<div style="display:flex;align-items:center;gap:6px;margin-bottom:2px;">'
            f'<span style="width:7px;height:7px;border-radius:50%;background:{dot_color};display:inline-block;"></span>'
            f'<span style="font-size:0.72rem;color:#64748B;font-weight:600;">{site_name}</span>'
            f'<span style="font-size:0.62rem;color:#94A3B8;margin-left:auto;">{date_str}</span>'
            f'</div>'
            f'<div style="font-size:1.2rem;font-weight:700;color:#1E293B;">{avg_price:,.0f} ₽</div>'
            f'<div style="font-size:0.65rem;color:#94A3B8;">{count} позиций</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

st.markdown('<div style="height:4px"></div>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Page: Каталог (объединённая: общая + детальная информация)
# ---------------------------------------------------------------------------

if page == "Каталог":
    st.subheader("Каталог товаров")

    details = fetch_product_details()
    if not details:
        st.info("Нет данных.")
    else:
        df = pd.DataFrame(details)
        df = df[df["source_site"].isin(selected_sites)]

        # Clean HTML
        for c in ["firmness", "height_cm", "filler", "cover_material", "weight_kg"]:
            if c in df.columns:
                df[c] = df[c].apply(strip_html)

        # Filters row
        f1, f2, f3 = st.columns([1, 1, 2])
        with f1:
            site_filter = st.selectbox(
                "Конкурент",
                ["Все"] + [SITE_NAMES[s] for s in selected_sites],
                index=0,
            )
        with f2:
            date_filter = st.date_input("Дата (от)", value=None, key="date_from")
        with f3:
            search = st.text_input("Поиск по названию", "", key="catalog_search")

        if site_filter != "Все":
            rev = {v: k for k, v in SITE_NAMES.items()}
            df = df[df["source_site"] == rev[site_filter]]
        if search:
            df = df[df["name"].str.contains(search, case=False, na=False)]
        if date_filter:
            df["_dt"] = pd.to_datetime(df["scraped_at"])
            df = df[df["_dt"].dt.date >= date_filter]
            df = df.drop(columns=["_dt"])

        # Prepare display
        df_d = df.copy()
        df_d["source_site"] = df_d["source_site"].map(SITE_NAMES)
        if "scraped_at" in df_d.columns:
            df_d["scraped_at"] = pd.to_datetime(df_d["scraped_at"]).dt.strftime("%d.%m.%Y")

        df_d = df_d.rename(columns={
            "name": "Название",
            "source_site": "Конкурент",
            "price_sale": "Цена",
            "price_original": "Без скидки",
            "firmness": "Жёсткость",
            "height_cm": "Высота",
            "filler": "Наполнитель",
            "cover_material": "Чехол",
            "weight_kg": "Вес",
            "scraped_at": "Дата",
        })

        show_cols = ["Название", "Конкурент", "Цена", "Без скидки",
                     "Жёсткость", "Высота", "Наполнитель", "Чехол", "Вес", "Дата"]
        show_cols = [c for c in show_cols if c in df_d.columns]

        st.dataframe(
            df_d[show_cols],
            use_container_width=True,
            hide_index=True,
            height=500,
            column_config={
                "Цена": st.column_config.NumberColumn(format="%.0f ₽", width="small"),
                "Без скидки": st.column_config.NumberColumn(format="%.0f ₽", width="small"),
                "Конкурент": st.column_config.TextColumn(width="small"),
                "Высота": st.column_config.TextColumn(width="small"),
                "Вес": st.column_config.TextColumn(width="small"),
                "Дата": st.column_config.TextColumn(width="small"),
            },
        )

        st.caption(f"Всего: {len(df_d)} товаров")

        # Export
        c1, c2, _ = st.columns([1, 1, 6])
        with c1:
            try:
                r = requests.get(f"{API_BASE}/export", timeout=60)
                r.raise_for_status()
                st.download_button("Excel", r.content, "lineaf_prices.xlsx",
                                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            except Exception:
                pass
        with c2:
            st.download_button("CSV", df.to_csv(index=False).encode("utf-8"), "lineaf_prices.csv", "text/csv")

# ---------------------------------------------------------------------------
# Page: Графики
# ---------------------------------------------------------------------------

elif page == "Графики":
    df_chart = df_all_prices[df_all_prices["source_site"].isin(selected_sites)].copy() if not df_all_prices.empty else pd.DataFrame()

    # --- Динамика цен ---
    st.subheader("Динамика цен")

    if not df_chart.empty:
        mode = st.radio("Режим", ["Один товар", "Все товары конкурента"], horizontal=True, key="dyn_mode")

        if mode == "Один товар":
            prods = df_chart[["product_id", "name", "source_site"]].drop_duplicates()
            prods["label"] = prods["name"] + " (" + prods["source_site"].map(SITE_NAMES) + ")"
            pid = st.selectbox("Товар", prods["product_id"].tolist(),
                               format_func=lambda p: prods.loc[prods["product_id"] == p, "label"].iloc[0])
            if pid:
                h = fetch_price_history(pid)
                if h:
                    fig = px.line(pd.DataFrame(h), x="scraped_at", y="price_sale",
                                 labels={"scraped_at": "Дата", "price_sale": "Цена (₽)"},
                                 title="Динамика цены")
                    fig.update_layout(template="plotly_white")
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("Данные появятся после повторного парсинга.")
        else:
            site = st.selectbox("Конкурент", selected_sites, format_func=lambda s: SITE_NAMES[s], key="dyn_site")
            sp = df_chart[df_chart["source_site"] == site]
            if not sp.empty:
                rows = []
                for _, r in sp.iterrows():
                    for item in fetch_price_history(r["product_id"]):
                        item["name"] = r["name"]
                        rows.append(item)
                if rows:
                    fig = px.line(pd.DataFrame(rows), x="scraped_at", y="price_sale", color="name",
                                 title=f"Динамика — {SITE_NAMES[site]}",
                                 labels={"scraped_at": "Дата", "price_sale": "Цена (₽)", "name": "Товар"})
                    fig.update_layout(template="plotly_white")
                    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # --- Средние цены (линейный график для динамики) ---
    st.subheader("Средние цены конкурентов")

    if not df_chart.empty:
        cmp_mode = st.radio("Показать", ["Все конкуренты", "Выбрать конкурента"], horizontal=True, key="cmp_mode")
        if cmp_mode == "Выбрать конкурента":
            cmp_site = st.selectbox("Конкурент", selected_sites, format_func=lambda s: SITE_NAMES[s], key="cmp_site")
            df_cmp = df_chart[df_chart["source_site"] == cmp_site].copy()
        else:
            df_cmp = df_chart.copy()

        if not df_cmp.empty:
            # Line chart grouped by site and date for future multi-snapshot support
            df_cmp["date"] = pd.to_datetime(df_cmp["scraped_at"]).dt.date
            avg = df_cmp.groupby(["source_site", "date"])["price_sale"].mean().reset_index()
            avg["source_site"] = avg["source_site"].map(SITE_NAMES)

            fig = px.line(avg, x="date", y="price_sale", color="source_site",
                          color_discrete_map=SITE_COLORS,
                          title="Средняя цена (динамика по датам сбора)",
                          labels={"date": "Дата", "price_sale": "Средняя цена (₽)", "source_site": "Конкурент"},
                          markers=True)
            fig.update_layout(template="plotly_white")
            st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # --- Распределение цен ---
    st.subheader("Распределение цен")

    if not df_chart.empty:
        dist_mode = st.radio("Показать", ["Все конкуренты", "Выбрать конкурента"], horizontal=True, key="dist_mode")
        if dist_mode == "Выбрать конкурента":
            dist_site = st.selectbox("Конкурент", selected_sites, format_func=lambda s: SITE_NAMES[s], key="dist_site")
            df_box = df_chart[df_chart["source_site"] == dist_site].copy()
        else:
            df_box = df_chart.copy()

        df_box["source_site"] = df_box["source_site"].map(SITE_NAMES)
        fig = px.box(df_box, x="source_site", y="price_sale", color="source_site",
                     color_discrete_map=SITE_COLORS, title="Распределение цен",
                     labels={"source_site": "Конкурент", "price_sale": "Цена (₽)"})
        fig.update_layout(template="plotly_white", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# Page: Изменения
# ---------------------------------------------------------------------------

elif page == "Изменения":
    st.subheader("Изменения в ассортименте и ценах")

    try:
        changes = fetch_changes()
    except Exception:
        changes = {"new": [], "removed": []}

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Новые товары**")
        new_p = changes.get("new", [])
        if new_p:
            df_n = pd.DataFrame(new_p)
            if "source_site" in df_n.columns:
                df_n["source_site"] = df_n["source_site"].map(SITE_NAMES)
            df_n = df_n.rename(columns={"name": "Название", "source_site": "Конкурент"})
            st.dataframe(df_n, use_container_width=True, hide_index=True)
        else:
            st.info("Нет новых товаров")

    with c2:
        st.markdown("**Удалённые товары**")
        rem_p = changes.get("removed", [])
        if rem_p:
            df_r = pd.DataFrame(rem_p)
            if "source_site" in df_r.columns:
                df_r["source_site"] = df_r["source_site"].map(SITE_NAMES)
            df_r = df_r.rename(columns={"name": "Название", "source_site": "Конкурент"})
            st.dataframe(df_r, use_container_width=True, hide_index=True)
        else:
            st.info("Нет удалённых товаров")

    st.divider()
    st.markdown("**Изменения цен**")
    st.caption("Сравнение цен между последними двумя парсингами. Появится после второго запуска.")

    if all_prices:
        df_p = pd.DataFrame(all_prices)
        df_p = df_p[df_p["source_site"].isin(selected_sites)]
        change_rows = []
        for _, row in df_p.iterrows():
            hist = fetch_price_history(row["product_id"])
            if len(hist) >= 2:
                prev_price = hist[-2].get("price_sale", 0) or 0
                curr_price = hist[-1].get("price_sale", 0) or 0
                if prev_price and prev_price != curr_price:
                    pct = ((curr_price - prev_price) / prev_price) * 100
                    change_rows.append({
                        "Название": row["name"],
                        "Конкурент": SITE_NAMES.get(row["source_site"], row["source_site"]),
                        "Была": prev_price,
                        "Стала": curr_price,
                        "Изменение %": pct,
                    })
        if change_rows:
            df_ch = pd.DataFrame(change_rows)
            st.dataframe(df_ch, use_container_width=True, hide_index=True,
                         column_config={
                             "Была": st.column_config.NumberColumn(format="%.0f ₽"),
                             "Стала": st.column_config.NumberColumn(format="%.0f ₽"),
                             "Изменение %": st.column_config.NumberColumn(format="%+.1f%%"),
                         })

# ---------------------------------------------------------------------------
# Page: Логи
# ---------------------------------------------------------------------------

elif page == "Логи":
    st.subheader("Журнал запусков")

    runs = fetch_runs()
    if runs:
        df_r = pd.DataFrame(runs)
        if "site" in df_r.columns:
            df_r["site"] = df_r["site"].map(SITE_NAMES)
        for dc in ["started_at", "finished_at"]:
            if dc in df_r.columns:
                df_r[dc] = pd.to_datetime(df_r[dc]).dt.strftime("%d.%m.%Y %H:%M")
        df_r = df_r.rename(columns={
            "id": "ID", "site": "Конкурент", "status": "Статус",
            "started_at": "Начало", "finished_at": "Конец",
            "products_found": "Найдено", "products_new": "Новых",
            "products_removed": "Удалено", "error_message": "Ошибка",
        })
        st.dataframe(df_r, use_container_width=True, hide_index=True)
    else:
        st.info("Нет записей.")

    st.divider()
    st.markdown("**Ручной запуск парсинга**")
    st.markdown(
        '<div style="background:#F1F5F9;border-radius:8px;padding:12px 16px;font-size:0.85rem;color:#475569;margin-bottom:12px;">'
        '<b>Зачем?</b> Внеплановый сбор цен со всех 3 сайтов. '
        'Полезно когда нужны свежие данные между еженедельными автозапусками.<br>'
        '<b>Время:</b> ~15–20 минут. Парсинг работает в фоне — можно продолжать работу.</div>',
        unsafe_allow_html=True,
    )
    if st.button("Запустить парсинг", type="primary"):
        try:
            requests.post(f"{API_BASE}/scrape", timeout=10).raise_for_status()
            st.success("Парсинг запущен. Обновите страницу через ~15–20 мин.")
        except Exception as e:
            st.error(f"Ошибка: {e}")
