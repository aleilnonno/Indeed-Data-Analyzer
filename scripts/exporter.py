import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

# Aggiornamento cartella di esportazione
EXPORT_DIR = "exported_data"
if os.path.exists(EXPORT_DIR):
    shutil.rmtree(EXPORT_DIR) 
os.makedirs(EXPORT_DIR)


# === CONFIGURAZIONE PRINCIPALE ===

BASE_URL = "https://data.indeed.com"

COUNTRIES_HEADLINE = {
    "Wages": [
        "United States",
        "Spain",
        "United Kingdom",
        "Japan",
        "Euro Area",
    ],
    "Artificial Intelligence": [
        "United States",
        "United Kingdom",
        "Germany",
        "Australia",
        "Ireland",
    ],
    "Job Postings": [
        "United States",
        "United Kingdom",
        "Spain",
        "Ireland",
        "Euro Area",
        "Australia",
    ],
}

COUNTRIES_SECTOR = { 
    "Wages": ["United States"], 
    "Job Postings": ["United States", 
                     "United Kingdom", 
                     "Australia"], 
    "Artificial Intelligence": [], # AI non ha sector
}


# === FUNZIONI DI SUPPORTO PER LA PAGINA ===

def go_to_dashboard(page, dashboard_name: str):

    # Aspetta che la pagina sia caricata
    page.wait_for_load_state("networkidle")
    page.wait_for_selector(".css-11dmwc2.eac13zx0", timeout=20000)

    if dashboard_name == "Job Postings":
        page.locator(".css-11dmwc2.eac13zx0").nth(1).click()
    elif dashboard_name == "Wages":
        page.locator(".css-11dmwc2.eac13zx0").nth(2).click()
    elif dashboard_name == "Artificial Intelligence":
        page.locator(".css-11dmwc2.eac13zx0").nth(4).click()

    page.wait_for_timeout(1500)


def set_series_type(page, series_type: str, dashboard: str):

    # La pagina AI non ha selettore
    if dashboard == "Artificial Intelligence":
        return

    if series_type == "headline":
        page.get_by_role("tab", name="Headline").click()
    elif series_type == "sector":
        page.get_by_role("tab", name="Sector").click()
    
    page.wait_for_timeout(1000)


def set_country_headline(page, dashboard: str):
    page.get_by_role("combobox").nth(0).click()

    for country in COUNTRIES_HEADLINE[dashboard]:
        page.get_by_role("menuitemcheckbox", name=country).click()
        page.wait_for_timeout(500)

    page.keyboard.press("Escape")
    page.wait_for_timeout(1000)


def set_country_sector(page, dashboard: str, country: str):

    # Apri la select dei paesi
    select = page.locator("select[placeholder='Select country']").first

    # Mappa dei valori
    value_map = {
        "United States": "US",
        "United Kingdom": "GB",
        "Australia": "AU",
        "Canada": "CA",
        "France": "FR",
        "Germany": "DE",
        }
    
    value = value_map[country]

    # Seleziona il paese (forzato perché il select può essere invisibile)
    select.select_option(value=value, force=True)
    page.wait_for_timeout(500)

    page.keyboard.press("Escape")
    page.wait_for_timeout(1000)


def set_all_sectors(page):
    
    # 1. Apri il combobox dei settori
    page.get_by_role("combobox").nth(1).click()

    # 2. Ottieni tutte le opzioni del listbox
    options = page.get_by_role("menuitemcheckbox")
    count = options.count()

    # 3. Seleziona solo quelle non selezionate
    for i in range(count):
        opt = options.nth(i)
        selected = opt.get_attribute("aria-checked")

        # Se non è selezionata → clicchiamo
        if selected != "true":
            opt.click()
            page.wait_for_timeout(1000)  # piccolo delay per evitare overload

    # 4. Chiudi il menu
    page.keyboard.press("Escape")
    page.wait_for_timeout(1000)

def export_csv(page, dashboard: str, series_type: str, country: str | None = None):
    
    # Costruisci il nome del file
    dash = dashboard.lower().replace(" ", "_")
    series = series_type.lower().replace(" ", "_")
    date_str = datetime.now(timezone.utc).strftime("%d_%m_%Y")

    if country:
        country_slug = country.lower().replace(" ", "_")
        filename = f"{date_str}_{dash}_{series}_{country_slug}.csv"
    else:
        filename = f"{date_str}_{dash}_{series}.csv"

    # Aspetta che la dashboard abbia finito di caricare
    page.wait_for_function("""
                           () => {
                           const btn = [...document.querySelectorAll('button')]
                                .find(b => b.textContent.includes('Loading'));
                           return !btn;
                        }
                    """, timeout=720_000)

    # 1. Apri il menu di download
    page.get_by_role("button", name="Download").click()

    # 3. Salva il file
    with page.expect_download() as download_info: 
        page.get_by_role("button", name="as CSV").click()
    download = download_info.value
    download.save_as(f"exported_data/{filename}")


def export_dataset(page, dashboard: str, series_type: str):
    # 1. Seleziona la tipologia (headline/sector)
    set_series_type(page, series_type, dashboard)

    # 2. Caso Sector con più paesi (es. Job Postings)
    if series_type == "sector" and len(COUNTRIES_SECTOR[dashboard]) > 1:
        countries = COUNTRIES_SECTOR[dashboard]

        for country in countries:
            # Seleziona il paese specifico
            set_country_sector(page, dashboard, country)

            # Seleziona TUTTI i settori
            set_all_sectors(page)

            # Esporta il CSV con il paese nel nome
            export_csv(page, dashboard, series_type, country)

        return  # Fine: abbiamo già esportato tutti i paesi

    # 3. Caso normale (Headline o Sector con 0–1 paesi)
    if series_type == "headline":
        set_country_headline(page, dashboard)
    elif series_type == "sector":
        set_all_sectors(page)

    # Esporta il CSV senza paese nel nome
    export_csv(page, dashboard, series_type)


# === MAIN: LISTA DELLE COMBINAZIONI CHE TI SERVONO ===

def main():
    DASHBOARD_SERIES = {
        "Wages": ["headline", "sector"],
        "Artificial Intelligence": ["headline"],
        "Job Postings": ["headline", "sector"],
    }

    p = sync_playwright().start()
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()

    try:
        page.goto("https://data.indeed.com", wait_until="load", timeout=30_000)
        print("Pagina caricata.")

        first = True

        for dashboard, series_list in DASHBOARD_SERIES.items():

        # Torna indietro SOLO dopo la prima dashboard
            if not first:
                page.go_back()
                page.wait_for_timeout(1500)
            else:
                first = False

            # Vai alla dashboard specifica
            go_to_dashboard(page, dashboard)
            print(f"\n=== Dashboard: {dashboard} ===")

            for series_type in series_list:
                print(f"Esporto: {dashboard} - {series_type}")
                export_dataset(page, dashboard, series_type)

        print("\nTutte le esportazioni completate.")

    except Exception as e:
        print("Errore:", e)

    finally:
        browser.close()
        p.stop()


if __name__ == "__main__":
    main()
