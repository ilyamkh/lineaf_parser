"""Lineaf — Streamlit dashboard for competitor price monitoring.

Redesigned with:
- Sticky header with freshness + KPIs
- Vertical navigation in sidebar
- Detailed product info tab
- Improved charts with competitor/product selectors
- Price change highlighting
"""

from __future__ import annotations

import os
import re

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
    page_icon="📊",
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
# Custom CSS — Data-Dense Dashboard style
# ---------------------------------------------------------------------------

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    /* Base typography */
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    /* Remove default Streamlit top padding — prevents title cutoff */
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 1rem;
        max-width: 1400px;
    }

    /* Hide Streamlit deploy button */
    .stDeployButton { display: none; }
    #MainMenu { visibility: hidden; }

    /* KPI metric cards — compact */
    [data-testid="stMetric"] {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 12px 16px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.75rem !important;
        font-weight: 500;
        color: #64748B !important;
        letter-spacing: 0.02em;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.15rem !important;
        font-weight: 700;
        color: #1E293B !important;
    }

    /* Sidebar navigation */
    section[data-testid="stSidebar"] {
        background: #F8FAFC;
        border-right: 1px solid #E2E8F0;
    }
    section[data-testid="stSidebar"] .stRadio [role="radiogroup"] {
        gap: 2px;
    }
    section[data-testid="stSidebar"] .stRadio [role="radio"] {
        padding: 8px 12px;
        border-radius: 6px;
        transition: background 0.15s;
    }
    section[data-testid="stSidebar"] .stRadio [role="radio"]:hover {
        background: #E2E8F0;
    }

    /* Data tables */
    .stDataFrame {
        border-radius: 8px;
        border: 1px solid #E2E8F0;
    }

    /* Subheaders */
    h3 {
        color: #1E293B;
        font-weight: 600;
        font-size: 1.1rem !important;
        margin-top: 0.5rem !important;
    }

    /* Dividers */
    hr {
        margin: 0.75rem 0;
        border-color: #E2E8F0;
    }

    /* Buttons */
    .stButton button {
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.15s;
    }
    .stButton button[kind="primary"] {
        background: #1E40AF;
    }
    .stButton button[kind="primary"]:hover {
        background: #1D4ED8;
    }

    /* Select boxes */
    .stSelectbox, .stMultiSelect {
        font-size: 0.9rem;
    }

    /* Plotly charts */
    .js-plotly-plot { border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Cached API helpers
# ---------------------------------------------------------------------------


@st.cache_data(ttl=60)
def fetch_prices() -> list[dict]:
    resp = requests.get(f"{API_BASE}/prices", timeout=30)
    resp.raise_for_status()
    return resp.json()


@st.cache_data(ttl=60)
def fetch_product_details() -> list[dict]:
    resp = requests.get(f"{API_BASE}/products/details", timeout=30)
    resp.raise_for_status()
    return resp.json()


@st.cache_data(ttl=60)
def fetch_price_history(product_id: int) -> list[dict]:
    resp = requests.get(
        f"{API_BASE}/prices/history",
        params={"product_id": product_id},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


@st.cache_data(ttl=60)
def fetch_price_index() -> list[dict]:
    resp = requests.get(f"{API_BASE}/prices/index", timeout=30)
    resp.raise_for_status()
    return resp.json()


@st.cache_data(ttl=60)
def fetch_runs() -> list[dict]:
    resp = requests.get(f"{API_BASE}/runs", params={"limit": 50}, timeout=30)
    resp.raise_for_status()
    return resp.json()


@st.cache_data(ttl=60)
def fetch_freshness() -> list[dict]:
    resp = requests.get(f"{API_BASE}/runs/freshness", timeout=30)
    resp.raise_for_status()
    return resp.json()


@st.cache_data(ttl=60)
def fetch_changes() -> dict:
    resp = requests.get(f"{API_BASE}/products/changes", timeout=30)
    resp.raise_for_status()
    return resp.json()


def strip_html(val):
    if not val:
        return val
    return re.sub(r"<[^>]+>", "", val).strip()


# ---------------------------------------------------------------------------
# Sidebar: Navigation + Filters
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown(
        '<div style="padding:8px 0 4px;font-size:1.3rem;font-weight:700;color:#1E40AF;">'
        'Lineaf</div>',
        unsafe_allow_html=True,
    )
    st.caption("Мониторинг цен конкурентов")
    st.divider()

    page = st.radio(
        "Навигация",
        ["Общая информация", "Детальная информация", "Графики", "Изменения", "Логи"],
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
# Header: Freshness + KPIs (compact, always visible)
# ---------------------------------------------------------------------------

try:
    freshness_data = fetch_freshness()
    index_data = fetch_price_index()
except requests.exceptions.ConnectionError:
    st.error("Не удалось подключиться к API. Убедитесь, что FastAPI сервер запущен.")
    st.stop()

# --- Compact KPI header ---
index_map = {item["site"]: item.get("avg_price_sale", 0) for item in (index_data or [])}
fresh_map = {item["site"]: item for item in (freshness_data or [])}

cols = st.columns(len(SITE_NAMES))
for col, (site_key, site_name) in zip(cols, SITE_NAMES.items()):
    fresh = fresh_map.get(site_key, {})
    is_stale = fresh.get("is_stale", True)
    last_success = fresh.get("last_success")
    avg_price = index_map.get(site_key, 0)

    if last_success:
        from datetime import datetime
        try:
            dt = datetime.fromisoformat(last_success)
            date_str = dt.strftime("%d.%m %H:%M")
        except (ValueError, TypeError):
            date_str = "—"
    else:
        date_str = "—"

    status_dot = "#22C55E" if not is_stale else "#EF4444"
    bg = SITE_BG_COLORS.get(site_name, "#F8FAFC")
    border_color = SITE_COLORS.get(site_name, "#3B82F6")

    with col:
        st.markdown(
            f'<div style="background:{bg};border:1px solid #E2E8F0;border-left:4px solid {border_color};'
            f'border-radius:8px;padding:10px 14px;">'
            f'<div style="display:flex;align-items:center;gap:6px;margin-bottom:4px;">'
            f'<span style="width:8px;height:8px;border-radius:50%;background:{status_dot};display:inline-block;"></span>'
            f'<span style="font-size:0.75rem;color:#64748B;font-weight:500;">{site_name}</span>'
            f'<span style="font-size:0.65rem;color:#94A3B8;margin-left:auto;">{date_str}</span>'
            f'</div>'
            f'<div style="font-size:1.15rem;font-weight:700;color:#1E293B;">'
            f'{avg_price:,.0f} ₽</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Page: Общая информация (Prices table)
# ---------------------------------------------------------------------------

if page == "Общая информация":
    st.subheader("Цены конкурентов")

    prices_raw = fetch_prices()
    if not prices_raw:
        st.info("Нет данных о ценах.")
    else:
        df = pd.DataFrame(prices_raw)

        # Filter by selected sites
        df = df[df["source_site"].isin(selected_sites)]

        # Competitor filter above table
        site_filter = st.selectbox(
            "Фильтр по конкуренту",
            options=["Все"] + [SITE_NAMES[s] for s in selected_sites],
            index=0,
        )
        if site_filter != "Все":
            reverse_map = {v: k for k, v in SITE_NAMES.items()}
            df = df[df["source_site"] == reverse_map[site_filter]]

        # Search
        search = st.text_input("🔍 Поиск по названию", "")
        if search:
            df = df[df["name"].str.contains(search, case=False, na=False)]

        # Prepare display
        df_display = df.copy()
        df_display["source_site"] = df_display["source_site"].map(lambda s: SITE_NAMES.get(s, s))
        df_display = df_display.rename(columns={
            "product_id": "ID",
            "name": "Название",
            "source_site": "Конкурент",
            "price_sale": "Цена со скидкой",
            "price_original": "Цена без скидки",
            "scraped_at": "Дата сбора",
        })

        # Format date
        if "Дата сбора" in df_display.columns:
            df_display["Дата сбора"] = pd.to_datetime(df_display["Дата сбора"]).dt.strftime("%d.%m.%Y %H:%M")

        st.dataframe(
            df_display,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Цена со скидкой": st.column_config.NumberColumn(format="%.0f ₽"),
                "Цена без скидки": st.column_config.NumberColumn(format="%.0f ₽"),
            },
        )

        # Export buttons
        col1, col2, _ = st.columns([1, 1, 4])
        with col1:
            try:
                export_resp = requests.get(f"{API_BASE}/export", timeout=60)
                export_resp.raise_for_status()
                st.download_button(
                    "📥 Excel", export_resp.content,
                    file_name="lineaf_prices.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            except Exception:
                st.warning("Ошибка экспорта Excel")
        with col2:
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("📥 CSV", csv, file_name="lineaf_prices.csv", mime="text/csv")

# ---------------------------------------------------------------------------
# Page: Детальная информация
# ---------------------------------------------------------------------------

elif page == "Детальная информация":
    st.subheader("Детальная информация о товарах")

    details = fetch_product_details()
    if not details:
        st.info("Нет данных.")
    else:
        df = pd.DataFrame(details)
        df = df[df["source_site"].isin(selected_sites)]

        # Clean HTML tags
        for col in ["firmness", "height_cm", "filler", "cover_material", "weight_kg"]:
            if col in df.columns:
                df[col] = df[col].apply(strip_html)

        # Competitor filter
        site_filter = st.selectbox(
            "Конкурент",
            options=["Все"] + [SITE_NAMES[s] for s in selected_sites],
            index=0,
            key="detail_site_filter",
        )
        if site_filter != "Все":
            reverse_map = {v: k for k, v in SITE_NAMES.items()}
            df = df[df["source_site"] == reverse_map[site_filter]]

        search = st.text_input("🔍 Поиск по названию", "", key="detail_search")
        if search:
            df = df[df["name"].str.contains(search, case=False, na=False)]

        df_display = df.copy()
        df_display["source_site"] = df_display["source_site"].map(lambda s: SITE_NAMES.get(s, s))
        df_display = df_display.rename(columns={
            "name": "Название",
            "source_site": "Конкурент",
            "price_sale": "Цена",
            "price_original": "Цена без скидки",
            "firmness": "Жёсткость",
            "height_cm": "Высота",
            "filler": "Наполнитель",
            "cover_material": "Чехол",
            "weight_kg": "Вес (кг)",
        })

        display_cols = ["Название", "Конкурент", "Цена", "Цена без скидки",
                        "Жёсткость", "Высота", "Наполнитель", "Чехол", "Вес (кг)"]
        display_cols = [c for c in display_cols if c in df_display.columns]

        st.dataframe(
            df_display[display_cols],
            use_container_width=True,
            hide_index=True,
            column_config={
                "Цена": st.column_config.NumberColumn(format="%.0f ₽"),
                "Цена без скидки": st.column_config.NumberColumn(format="%.0f ₽"),
            },
        )

        st.caption(f"Всего товаров: {len(df_display)}")

# ---------------------------------------------------------------------------
# Page: Графики
# ---------------------------------------------------------------------------

elif page == "Графики":
    prices_raw = fetch_prices()
    df_all = pd.DataFrame(prices_raw) if prices_raw else pd.DataFrame()
    df_all = df_all[df_all["source_site"].isin(selected_sites)] if not df_all.empty else df_all

    # --- Динамика товара ---
    st.subheader("📉 Динамика цен")

    if not df_all.empty:
        chart_mode = st.radio(
            "Режим",
            ["Один товар", "Все товары конкурента"],
            horizontal=True,
            key="dynamics_mode",
        )

        if chart_mode == "Один товар":
            products = df_all[["product_id", "name", "source_site"]].drop_duplicates()
            products["label"] = products["name"] + " (" + products["source_site"].map(SITE_NAMES) + ")"
            selected_pid = st.selectbox(
                "Выберите товар",
                options=products["product_id"].tolist(),
                format_func=lambda pid: products.loc[products["product_id"] == pid, "label"].iloc[0],
            )
            if selected_pid:
                hist = fetch_price_history(selected_pid)
                if hist:
                    df_h = pd.DataFrame(hist)
                    fig = px.line(df_h, x="scraped_at", y="price_sale",
                                 title="Динамика цены",
                                 labels={"scraped_at": "Дата", "price_sale": "Цена (₽)"})
                    fig.update_layout(template="plotly_white")
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("Нет истории цен. Данные появятся после повторного парсинга.")
        else:
            site_choice = st.selectbox(
                "Конкурент",
                options=selected_sites,
                format_func=lambda s: SITE_NAMES.get(s, s),
                key="dynamics_site",
            )
            site_products = df_all[df_all["source_site"] == site_choice]
            if not site_products.empty:
                # Fetch history for all products of this site
                all_hist = []
                for _, row in site_products.iterrows():
                    h = fetch_price_history(row["product_id"])
                    for item in h:
                        item["name"] = row["name"]
                    all_hist.extend(h)
                if all_hist:
                    df_h = pd.DataFrame(all_hist)
                    fig = px.line(df_h, x="scraped_at", y="price_sale", color="name",
                                 title=f"Динамика цен — {SITE_NAMES[site_choice]}",
                                 labels={"scraped_at": "Дата", "price_sale": "Цена (₽)", "name": "Товар"})
                    fig.update_layout(template="plotly_white", showlegend=True)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("Нет истории цен.")

    st.divider()

    # --- Сравнение конкурентов (средние цены) ---
    st.subheader("📊 Средние цены конкурентов")

    if not df_all.empty:
        compare_mode = st.radio(
            "Показать",
            ["Все конкуренты", "Выбрать конкурента"],
            horizontal=True,
            key="compare_mode",
        )

        if compare_mode == "Выбрать конкурента":
            compare_site = st.selectbox(
                "Конкурент",
                options=selected_sites,
                format_func=lambda s: SITE_NAMES.get(s, s),
                key="compare_site",
            )
            df_comp = df_all[df_all["source_site"] == compare_site].copy()
        else:
            df_comp = df_all.copy()

        if not df_comp.empty:
            # Group by site — show bar chart (we have one time slice)
            avg_by_site = df_comp.groupby("source_site")["price_sale"].mean().reset_index()
            avg_by_site["source_site"] = avg_by_site["source_site"].map(SITE_NAMES)
            avg_by_site.columns = ["Конкурент", "Средняя цена"]

            fig_bar = px.bar(
                avg_by_site, x="Конкурент", y="Средняя цена",
                color="Конкурент",
                color_discrete_map=SITE_COLORS,
                title="Средняя цена по конкурентам",
                labels={"Средняя цена": "Средняя цена (₽)"},
                text_auto=".0f",
            )
            fig_bar.update_layout(template="plotly_white", showlegend=False)
            st.plotly_chart(fig_bar, use_container_width=True)

    st.divider()

    # --- Распределение цен ---
    st.subheader("📦 Распределение цен")

    if not df_all.empty:
        dist_mode = st.radio(
            "Показать",
            ["Все конкуренты", "Выбрать конкурента"],
            horizontal=True,
            key="dist_mode",
        )

        if dist_mode == "Выбрать конкурента":
            dist_site = st.selectbox(
                "Конкурент",
                options=selected_sites,
                format_func=lambda s: SITE_NAMES.get(s, s),
                key="dist_site",
            )
            df_box = df_all[df_all["source_site"] == dist_site].copy()
        else:
            df_box = df_all.copy()

        df_box = df_box.copy()
        df_box["source_site"] = df_box["source_site"].map(SITE_NAMES)

        fig_box = px.box(
            df_box, x="source_site", y="price_sale",
            color="source_site",
            color_discrete_map=SITE_COLORS,
            title="Распределение цен",
            labels={"source_site": "Конкурент", "price_sale": "Цена (₽)"},
        )
        fig_box.update_layout(template="plotly_white", showlegend=False)
        st.plotly_chart(fig_box, use_container_width=True)

# ---------------------------------------------------------------------------
# Page: Изменения
# ---------------------------------------------------------------------------

elif page == "Изменения":
    st.subheader("Изменения в ассортименте и ценах")

    try:
        changes = fetch_changes()
    except Exception:
        changes = {"new": [], "removed": []}

    col_new, col_rem = st.columns(2)

    with col_new:
        st.markdown("#### 🆕 Новые товары")
        new_products = changes.get("new", [])
        if new_products:
            df_new = pd.DataFrame(new_products)
            if "source_site" in df_new.columns:
                df_new["source_site"] = df_new["source_site"].map(SITE_NAMES)
            df_new = df_new.rename(columns={"name": "Название", "source_site": "Конкурент"})
            st.dataframe(df_new, use_container_width=True, hide_index=True)
        else:
            st.info("Нет новых товаров")

    with col_rem:
        st.markdown("#### ❌ Удалённые товары")
        removed_products = changes.get("removed", [])
        if removed_products:
            df_rem = pd.DataFrame(removed_products)
            if "source_site" in df_rem.columns:
                df_rem["source_site"] = df_rem["source_site"].map(SITE_NAMES)
            df_rem = df_rem.rename(columns={"name": "Название", "source_site": "Конкурент"})
            st.dataframe(df_rem, use_container_width=True, hide_index=True)
        else:
            st.info("Нет удалённых товаров")

    st.divider()

    # Price changes (when we have >1 snapshots)
    st.markdown("#### 💰 Изменения цен")
    st.caption("Изменения цен будут отображаться после второго запуска парсинга (нужно минимум 2 среза данных)")

    prices = fetch_prices()
    if prices:
        df_prices = pd.DataFrame(prices)
        df_prices = df_prices[df_prices["source_site"].isin(selected_sites)]

        # For each product, check if we have >1 snapshot
        has_changes = False
        change_rows = []
        for _, row in df_prices.iterrows():
            hist = fetch_price_history(row["product_id"])
            if len(hist) >= 2:
                has_changes = True
                prev = hist[-2]
                curr = hist[-1]
                prev_price = prev.get("price_sale", 0) or 0
                curr_price = curr.get("price_sale", 0) or 0
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
            df_changes = pd.DataFrame(change_rows)
            # Color formatting via column_config
            st.dataframe(
                df_changes,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Была": st.column_config.NumberColumn(format="%.0f ₽"),
                    "Стала": st.column_config.NumberColumn(format="%.0f ₽"),
                    "Изменение %": st.column_config.NumberColumn(
                        format="%.1f%%",
                        help="Зелёный — цена выросла (конкурент поднял цену), Красный — упала",
                    ),
                },
            )
        elif not has_changes:
            st.info("📊 Пока доступен только один срез данных. После повторного парсинга здесь появится сравнение цен.")

# ---------------------------------------------------------------------------
# Page: Логи
# ---------------------------------------------------------------------------

elif page == "Логи":
    st.subheader("Журнал запусков парсинга")

    runs_data = fetch_runs()
    if runs_data:
        df_runs = pd.DataFrame(runs_data)
        if "site" in df_runs.columns:
            df_runs["site"] = df_runs["site"].map(SITE_NAMES)

        # Format dates
        for date_col in ["started_at", "finished_at"]:
            if date_col in df_runs.columns:
                df_runs[date_col] = pd.to_datetime(df_runs[date_col]).dt.strftime("%d.%m.%Y %H:%M")

        df_runs = df_runs.rename(columns={
            "id": "ID", "site": "Конкурент", "status": "Статус",
            "started_at": "Начало", "finished_at": "Конец",
            "products_found": "Найдено", "products_new": "Новых",
            "products_removed": "Удалено", "error_message": "Ошибка",
        })

        st.dataframe(df_runs, use_container_width=True, hide_index=True)
    else:
        st.info("Нет записей о запусках.")

    st.divider()

    # Manual scrape section with instructions
    st.markdown("#### 🔄 Ручной запуск парсинга")
    st.markdown("""
    **Зачем эта кнопка?**
    Нажмите, чтобы запустить внеплановый сбор цен со всех 3 сайтов.
    Полезно когда нужны свежие данные между еженедельными автозапусками.

    **Среднее время парсинга:** ~15-20 минут (3 сайта последовательно).
    Парсинг запускается в фоне — можно продолжать работу с дашбордом.
    После завершения обновите страницу, чтобы увидеть новые данные.
    """)

    col_btn, col_status = st.columns([1, 3])
    with col_btn:
        if st.button("🚀 Запустить парсинг", type="primary"):
            try:
                scrape_resp = requests.post(f"{API_BASE}/scrape", timeout=10)
                scrape_resp.raise_for_status()
                st.success("✅ Парсинг запущен в фоне! Обновите страницу через ~15-20 минут.")
            except Exception as exc:
                st.error(f"❌ Ошибка запуска: {exc}")
