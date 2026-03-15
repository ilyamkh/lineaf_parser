"""Lineaf -- Streamlit dashboard for competitor price monitoring."""

from __future__ import annotations

import os

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(page_title="Lineaf — Цены конкурентов", layout="wide")
st.title("Lineaf — Цены конкурентов")

API_BASE = os.environ.get("API_BASE_URL", "http://localhost:8000/api")

SITE_NAMES: dict[str, str] = {
    "askona": "Аскона",
    "ormatek": "Орматек",
    "sonum": "Сонум",
}

# ---------------------------------------------------------------------------
# Cached API helpers
# ---------------------------------------------------------------------------


@st.cache_data(ttl=60)
def fetch_prices(sites: tuple[str, ...]) -> list[dict]:
    params = [("site", s) for s in sites]
    resp = requests.get(f"{API_BASE}/prices", params=params, timeout=30)
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


# ---------------------------------------------------------------------------
# Sidebar filters
# ---------------------------------------------------------------------------

st.sidebar.header("Фильтры")

selected_sites: list[str] = st.sidebar.multiselect(
    "Конкурент",
    options=list(SITE_NAMES.keys()),
    default=list(SITE_NAMES.keys()),
    format_func=lambda s: SITE_NAMES.get(s, s),
)

if not selected_sites:
    st.warning("Выберите хотя бы одного конкурента в боковой панели.")
    st.stop()

# ---------------------------------------------------------------------------
# Freshness indicator (above tabs)
# ---------------------------------------------------------------------------

st.subheader("Свежесть данных")

try:
    freshness_data = fetch_freshness()
    if freshness_data:
        fresh_cols = st.columns(len(freshness_data))
        for col, item in zip(fresh_cols, freshness_data):
            site_label = SITE_NAMES.get(item["site"], item["site"])
            is_stale = item.get("is_stale", True)
            last_success = item.get("last_success")

            if is_stale:
                label = f":red[{site_label}]"
            else:
                label = f":green[{site_label}]"

            if last_success:
                from datetime import datetime

                try:
                    dt = datetime.fromisoformat(last_success)
                    value = dt.strftime("%d.%m.%Y %H:%M")
                except (ValueError, TypeError):
                    value = str(last_success)
            else:
                value = "Нет данных"

            col.metric(label=label, value=value)
except requests.exceptions.ConnectionError:
    st.warning("Не удалось подключиться к API. Убедитесь, что FastAPI сервер запущен.")
    st.stop()

# ---------------------------------------------------------------------------
# KPI row (above tabs)
# ---------------------------------------------------------------------------

st.subheader("Средние цены")

try:
    index_data = fetch_price_index()
    if index_data:
        kpi_cols = st.columns(len(index_data))
        for col, item in zip(kpi_cols, index_data):
            site_label = SITE_NAMES.get(item["site"], item["site"])
            avg_price = item.get("avg_price_sale", 0)
            col.metric(
                label=f"Средняя цена — {site_label}",
                value=f"{avg_price:,.0f} руб.",
            )
except Exception:
    st.info("Данные средних цен пока недоступны.")

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tab_prices, tab_charts, tab_changes, tab_logs = st.tabs(
    ["Цены", "Графики", "Изменения", "Логи"]
)

# ---- Tab 1: Цены ----

with tab_prices:
    prices_raw = fetch_prices(tuple(selected_sites))
    if not prices_raw:
        st.info("Нет данных о ценах для выбранных конкурентов.")
    else:
        df_prices = pd.DataFrame(prices_raw)

        # Rename columns to Russian for display
        display_columns = {
            "product_id": "ID товара",
            "name": "Название",
            "source_site": "Конкурент",
            "price_sale": "Цена со скидкой",
            "price_original": "Цена без скидки",
            "scraped_at": "Дата сбора",
        }
        df_display = df_prices.rename(
            columns={k: v for k, v in display_columns.items() if k in df_prices.columns}
        )

        # Map site names to Russian
        if "Конкурент" in df_display.columns:
            df_display["Конкурент"] = df_display["Конкурент"].map(
                lambda s: SITE_NAMES.get(s, s)
            )

        # Name search filter
        search_query = st.text_input("Поиск по названию", "", key="price_search")
        if search_query:
            mask = df_display["Название"].str.contains(
                search_query, case=False, na=False
            )
            df_display = df_display[mask]

        st.dataframe(df_display, use_container_width=True)

        # Export: Excel
        col_exp1, col_exp2 = st.columns(2)
        with col_exp1:
            try:
                export_resp = requests.get(
                    f"{API_BASE}/export",
                    params={"site": selected_sites[0]},
                    timeout=60,
                )
                export_resp.raise_for_status()
                st.download_button(
                    label="Экспорт в Excel",
                    data=export_resp.content,
                    file_name="lineaf_prices.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            except Exception:
                st.warning("Не удалось получить Excel-файл от API.")

        # Export: CSV
        with col_exp2:
            csv_data = df_prices.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="Экспорт в CSV",
                data=csv_data,
                file_name="lineaf_prices.csv",
                mime="text/csv",
            )

# ---- Tab 2: Графики ----

with tab_charts:
    prices_for_charts = fetch_prices(tuple(selected_sites))
    df_chart = pd.DataFrame(prices_for_charts) if prices_for_charts else pd.DataFrame()

    # 2a. Динамика товара
    st.subheader("Динамика товара")
    if not df_chart.empty and "product_id" in df_chart.columns:
        product_options = (
            df_chart[["product_id", "name"]]
            .drop_duplicates(subset=["product_id"])
            .reset_index(drop=True)
        )
        selected_product = st.selectbox(
            "Выберите товар",
            options=product_options["product_id"].tolist(),
            format_func=lambda pid: product_options.loc[
                product_options["product_id"] == pid, "name"
            ].iloc[0],
        )

        if selected_product is not None:
            history = fetch_price_history(selected_product)
            if history:
                df_hist = pd.DataFrame(history)
                fig_hist = px.line(
                    df_hist,
                    x="scraped_at",
                    y="price_sale",
                    title="Динамика цены",
                    labels={
                        "scraped_at": "Дата",
                        "price_sale": "Цена со скидкой (руб.)",
                    },
                )
                st.plotly_chart(fig_hist, key="product_history")
            else:
                st.info("Нет истории цен для выбранного товара.")
    else:
        st.info("Нет данных для построения графика.")

    # 2b. Сравнение конкурентов
    st.subheader("Сравнение конкурентов")
    if not df_chart.empty and "scraped_at" in df_chart.columns:
        df_comp = (
            df_chart.groupby(["source_site", "scraped_at"])["price_sale"]
            .mean()
            .reset_index()
        )
        df_comp["source_site"] = df_comp["source_site"].map(
            lambda s: SITE_NAMES.get(s, s)
        )
        fig_comp = px.line(
            df_comp,
            x="scraped_at",
            y="price_sale",
            color="source_site",
            title="Сравнение средних цен конкурентов",
            labels={
                "scraped_at": "Дата",
                "price_sale": "Средняя цена (руб.)",
                "source_site": "Конкурент",
            },
        )
        st.plotly_chart(fig_comp, key="competitor_comparison")
    else:
        st.info("Нет данных для сравнения.")

    # 2c. Распределение цен
    st.subheader("Распределение цен")
    if not df_chart.empty and "price_sale" in df_chart.columns:
        df_box = df_chart.copy()
        df_box["source_site"] = df_box["source_site"].map(
            lambda s: SITE_NAMES.get(s, s)
        )
        fig_box = px.box(
            df_box,
            x="source_site",
            y="price_sale",
            color="source_site",
            title="Распределение цен по конкурентам",
            labels={
                "source_site": "Конкурент",
                "price_sale": "Цена со скидкой (руб.)",
            },
        )
        st.plotly_chart(fig_box, key="price_distribution")
    else:
        st.info("Нет данных для распределения.")

# ---- Tab 3: Изменения ----

with tab_changes:
    try:
        changes = fetch_changes()
        col_new, col_removed = st.columns(2)

        with col_new:
            st.subheader("Новые товары")
            new_products = changes.get("new", [])
            if new_products:
                df_new = pd.DataFrame(new_products)
                if "source_site" in df_new.columns:
                    df_new["source_site"] = df_new["source_site"].map(
                        lambda s: SITE_NAMES.get(s, s)
                    )
                df_new = df_new.rename(
                    columns={"name": "Название", "source_site": "Конкурент"}
                )
                st.dataframe(df_new, use_container_width=True)
            else:
                st.info("Нет новых товаров за последний период.")

        with col_removed:
            st.subheader("Удалённые товары")
            removed_products = changes.get("removed", [])
            if removed_products:
                df_removed = pd.DataFrame(removed_products)
                if "source_site" in df_removed.columns:
                    df_removed["source_site"] = df_removed["source_site"].map(
                        lambda s: SITE_NAMES.get(s, s)
                    )
                df_removed = df_removed.rename(
                    columns={"name": "Название", "source_site": "Конкурент"}
                )
                st.dataframe(df_removed, use_container_width=True)
            else:
                st.info("Нет удалённых товаров за последний период.")

    except Exception:
        st.info("Нет изменений за последний период")

# ---- Tab 4: Логи ----

with tab_logs:
    runs_data = fetch_runs()
    if runs_data:
        df_runs = pd.DataFrame(runs_data)

        # Map site names to Russian
        if "site" in df_runs.columns:
            df_runs["site"] = df_runs["site"].map(lambda s: SITE_NAMES.get(s, s))

        display_runs_cols = {
            "id": "ID",
            "site": "Конкурент",
            "status": "Статус",
            "started_at": "Начало",
            "finished_at": "Конец",
            "products_found": "Найдено",
            "products_new": "Новых",
            "products_removed": "Удалено",
            "error_message": "Ошибка",
        }
        df_runs = df_runs.rename(
            columns={k: v for k, v in display_runs_cols.items() if k in df_runs.columns}
        )
        st.dataframe(df_runs, use_container_width=True)
    else:
        st.info("Нет записей о запусках парсинга.")

    st.divider()

    if st.button("Запустить парсинг", type="primary"):
        try:
            scrape_resp = requests.post(f"{API_BASE}/scrape", timeout=10)
            scrape_resp.raise_for_status()
            st.success("Парсинг запущен в фоне")
        except Exception as exc:
            st.error(f"Ошибка запуска парсинга: {exc}")
