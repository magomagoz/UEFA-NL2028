import streamlit as st
import math
import pandas as pd
from collections import defaultdict
from fpdf import FPDF
import matplotlib.pyplot as plt
import tempfile
import urllib.request
import datetime
import os

# --- 1. CONFIGURAZIONE PAGINA (Primo comando assoluto) ---
st.set_page_config(page_title="Nations League Predictor Live", page_icon="⚽", layout="wide")

# --- 2. CARICAMENTO CALENDARIO BASE (Nations League) ---
@st.cache_data
def carica_calendario_csv():
    try:
        # Modificato per leggere il calendario della Nations League
        df = pd.read_csv("calendario_nations_league.csv", sep=";")
        df['Data'] = df['Data'].astype(str)
        df['Ora'] = df['Ora'].astype(str)
        df['Girone'] = df['Girone'].fillna('').astype(str).apply(
            lambda x: f"Gruppo {x}" if x.strip() != "" else "Fase Finale"
        )
        df['Casa'] = df['Casa'].astype(str).str.strip()
        df['Fuori'] = df['Fuori'].astype(str).str.strip()
        df['Etichetta_Menu'] = df['Data'] + " - " + df['Ora'] + " - " + df['Girone'] + " | " + df['Casa'] + " vs " + df['Fuori']
        return df
    except Exception as e:
        st.error(f"Errore critico nel caricamento del file calendario_nations_league.csv: {e}")
        return pd.DataFrame(columns=["Data", "Ora", "Girone", "Casa", "Fuori", "Etichetta_Menu"])

df_calendario = carica_calendario_csv()

# --- 3. INIZIALIZZAZIONE STRUTTURA RISULTATI IN MEMORIA ---
if 'df_risultati' not in st.session_state:
    init_data = []
    if not df_calendario.empty:
        for idx, row in df_calendario.iterrows():
            init_data.append({
                "ID_Match": idx, 
                "Match": row['Etichetta_Menu'],
                "Casa": row['Casa'], 
                "Ospite": row['Fuori'], 
                "Gol Casa": 0, 
                "Gol Ospite": 0, 
                "Giocata": False
            })
    st.session_state.df_risultati = pd.DataFrame(init_data)

# --- 4. GESTIONE SALVATAGGI: CARICAMENTO FILE STORICO (Upload) ---
st.sidebar.header("💾 Carica Salvataggio")
storico_file = st.sidebar.file_uploader("Ripristina i risultati salvati (CSV)", type=['csv'], help="Carica qui il file 'risultati_nations_salvati.csv' che hai scaricato in precedenza.")

if storico_file is not None:
    if st.session_state.get('last_loaded_file') != storico_file.name:
        try:
            df_salvato = pd.read_csv(storico_file, sep=";")
            df_base = st.session_state.df_risultati.drop(columns=["Gol Casa", "Gol Ospite", "Giocata"])
            df_merged = pd.merge(df_base, df_salvato[["ID_Match", "Gol Casa", "Gol Ospite", "Giocata"]], on="ID_Match", how="left")
            
            df_merged["Gol Casa"] = df_merged["Gol Casa"].fillna(0).astype(int)
            df_merged["Gol Ospite"] = df_merged["Gol Ospite"].fillna(0).astype(int)
            df_merged["Giocata"] = df_merged["Giocata"].fillna(False).astype(bool)
            
            st.session_state.df_risultati = df_merged
            st.session_state.last_loaded_file = storico_file.name
            st.sidebar.success("✅ Salvataggio ripristinato con successo!")
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"Errore durante il caricamento del salvataggio: {e}")

st.sidebar.markdown("---")

# --- 5. INTERFACCIA GRAFICA: BANNER ---
st.image("banner1.png", use_container_width=True)
st.write("Inserisci i risultati reali della Nations League, poi **salva il file** per non perderli. Il sistema ricalcolerà la forza delle Nazionali europee per i pronostici futuri.")

# --- 6. BASELINE STRUTTURA SQUADRE EUROPEE (Nations League) ---
scout_ratings_base = {
    # --- LEGA A & B (Top & Medium Tier) ---
    'Francia': {'attacco': 1.85, 'difesa': 0.65, 'flag': '🇫🇷'}, 'Spagna': {'attacco': 1.80, 'difesa': 0.65, 'flag': '🇪🇸'},
    'Inghilterra': {'attacco': 1.80, 'difesa': 0.65, 'flag': '🇬🇧'}, 'Portogallo': {'attacco': 1.75, 'difesa': 0.70, 'flag': '🇵🇹'},
    'Germania': {'attacco': 1.70, 'difesa': 0.75, 'flag': '🇩🇪'}, 'Olanda': {'attacco': 1.65, 'difesa': 0.75, 'flag': '🇳🇱'},
    'Italia': {'attacco': 1.60, 'difesa': 0.70, 'flag': '🇮🇹'}, 'Belgio': {'attacco': 1.55, 'difesa': 0.80, 'flag': '🇧🇪'},
    'Croazia': {'attacco': 1.45, 'difesa': 0.80, 'flag': '🇭🇷'}, 'Danimarca': {'attacco': 1.35, 'difesa': 0.80, 'flag': '🇩🇰'},
    'Svizzera': {'attacco': 1.30, 'difesa': 0.85, 'flag': '🇨🇭'}, 'Austria': {'attacco': 1.30, 'difesa': 0.85, 'flag': '🇦🇹'},
    'Serbia': {'attacco': 1.35, 'difesa': 0.95, 'flag': '🇷🇸'}, 'Polonia': {'attacco': 1.30, 'difesa': 0.90, 'flag': '🇵🇱'},
    'Ucraina': {'attacco': 1.25, 'difesa': 0.90, 'flag': '🇺🇦'}, 'Ungheria': {'attacco': 1.25, 'difesa': 0.90, 'flag': '🇭🇺'},
    'Turchia': {'attacco': 1.30, 'difesa': 0.90, 'flag': '🇹🇷'}, 'Svezia': {'attacco': 1.30, 'difesa': 0.90, 'flag': '🇸🇪'},
    'Norvegia': {'attacco': 1.40, 'difesa': 0.95, 'flag': '🇳🇴'}, 'Scozia': {'attacco': 1.20, 'difesa': 0.95, 'flag': '🏴󠁧󠁢󠁳󠁣󠁴󠁿'},
    'Galles': {'attacco': 1.15, 'difesa': 0.95, 'flag': '🏴󠁧󠁢󠁷󠁬󠁳󠁿'}, 'Repubblica Ceca': {'attacco': 1.20, 'difesa': 0.95, 'flag': '🇨🇿'},
    'Grecia': {'attacco': 1.15, 'difesa': 0.85, 'flag': '🇬🇷'}, 'Romania': {'attacco': 1.10, 'difesa': 0.90, 'flag': '🇷🇴'},
    'Slovacchia': {'attacco': 1.10, 'difesa': 0.95, 'flag': '🇸🇰'}, 'Slovenia': {'attacco': 1.05, 'difesa': 0.90, 'flag': '🇸🇮'},
    'Irlanda': {'attacco': 1.00, 'difesa': 1.00, 'flag': '🇮🇪'}, 'Finlandia': {'attacco': 1.00, 'difesa': 1.00, 'flag': '🇫🇮'},
    'Albania': {'attacco': 1.05, 'difesa': 0.95, 'flag': '🇦🇱'}, 'Montenegro': {'attacco': 1.00, 'difesa': 1.00, 'flag': '🇲🇪'},
    'Islanda': {'attacco': 1.00, 'difesa': 1.05, 'flag': '🇮🇸'}, 'Bosnia Erzegovina': {'attacco': 1.05, 'difesa': 1.05, 'flag': '🇧🇦'},
    'Israele': {'attacco': 1.10, 'difesa': 1.10, 'flag': '🇮🇱'}, 'Georgia': {'attacco': 1.10, 'difesa': 1.05, 'flag': '🇬🇪'},
    
    # --- LEGA C & D (Lower Tier) ---
    'Bulgaria': {'attacco': 0.90, 'difesa': 1.05, 'flag': '🇧🇬'}, 'Lussemburgo': {'attacco': 0.90, 'difesa': 1.10, 'flag': '🇱🇺'},
    'Kosovo': {'attacco': 1.00, 'difesa': 1.05, 'flag': '🇽🇰'}, 'Kazakistan': {'attacco': 0.90, 'difesa': 1.10, 'flag': '🇰🇿'},
    'Armenia': {'attacco': 0.90, 'difesa': 1.15, 'flag': '🇦🇲'}, 'Cipro': {'attacco': 0.85, 'difesa': 1.20, 'flag': '🇨🇾'},
    'Bielorussia': {'attacco': 0.85, 'difesa': 1.15, 'flag': '🇧🇾'}, 'Lituania': {'attacco': 0.80, 'difesa': 1.20, 'flag': '🇱🇹'},
    'Estonia': {'attacco': 0.80, 'difesa': 1.25, 'flag': '🇪🇪'}, 'Lettonia': {'attacco': 0.85, 'difesa': 1.20, 'flag': '🇱🇻'},
    'Far Oer': {'attacco': 0.75, 'difesa': 1.30, 'flag': '🇫🇴'}, 'Macedonia del Nord': {'attacco': 0.95, 'difesa': 1.10, 'flag': '🇲🇰'},
    'Moldavia': {'attacco': 0.75, 'difesa': 1.35, 'flag': '🇲🇩'}, 'Malta': {'attacco': 0.70, 'difesa': 1.40, 'flag': '🇲🇹'},
    'Andorra': {'attacco': 0.65, 'difesa': 1.45, 'flag': '🇦🇩'}, 'San Marino': {'attacco': 0.50, 'difesa': 1.60, 'flag': '🇸🇲'},
    'Liechtenstein': {'attacco': 0.60, 'difesa': 1.50, 'flag': '🇱🇮'}, 'Gibilterra': {'attacco': 0.55, 'difesa': 1.55, 'flag': '🇬🇮'}
}

iso_map = {
    'Francia': 'fr', 'Spagna': 'es', 'Inghilterra': 'gb-eng', 'Portogallo': 'pt',
    'Germania': 'de', 'Olanda': 'nl', 'Italia': 'it', 'Belgio': 'be',
    'Croazia': 'hr', 'Danimarca': 'dk', 'Svizzera': 'ch', 'Austria': 'at',
    'Serbia': 'rs', 'Polonia': 'pl', 'Ucraina': 'ua', 'Ungheria': 'hu',
    'Turchia': 'tr', 'Svezia': 'se', 'Norvegia': 'no', 'Scozia': 'gb-sct',
    'Galles': 'gb-wls', 'Repubblica Ceca': 'cz', 'Grecia': 'gr', 'Romania': 'ro',
    'Slovacchia': 'sk', 'Slovenia': 'si', 'Irlanda': 'ie', 'Finlandia': 'fi',
    'Albania': 'al', 'Montenegro': 'me', 'Islanda': 'is', 'Bosnia Erzegovina': 'ba',
    'Israele': 'il', 'Georgia': 'ge', 'Bulgaria': 'bg', 'Lussemburgo': 'lu',
    'Kosovo': 'xk', 'Kazakistan': 'kz', 'Armenia': 'am', 'Cipro': 'cy',
    'Bielorussia': 'by', 'Lituania': 'lt', 'Estonia': 'ee', 'Lettonia': 'lv',
    'Far Oer': 'fo', 'Macedonia del Nord': 'mk', 'Moldavia': 'md', 'Malta': 'mt',
    'Andorra': 'ad', 'San Marino': 'sm', 'Liechtenstein': 'li', 'Gibilterra': 'gi'
}

iso_map = {
    'Francia': 'fr', 'Spagna': 'es', 'Inghilterra': 'gb-eng', 'Portogallo': 'pt',
    'Germania': 'de', 'Olanda': 'nl', 'Italia': 'it', 'Belgio': 'be',
    'Croazia': 'hr', 'Danimarca': 'dk', 'Svizzera': 'ch', 'Austria': 'at',
    'Serbia': 'rs', 'Polonia': 'pl', 'Ucraina': 'ua', 'Ungheria': 'hu',
    'Turchia': 'tr', 'Svezia': 'se', 'Norvegia': 'no', 'Scozia': 'gb-sct',
    'Galles': 'gb-wls', 'Repubblica Ceca': 'cz', 'Grecia': 'gr', 'Romania': 'ro',
    'Slovacchia': 'sk', 'Slovenia': 'si', 'Irlanda': 'ie', 'Finlandia': 'fi',
    'Albania': 'al', 'Montenegro': 'me', 'Islanda': 'is', 'Bosnia Erzegovina': 'ba',
    'Israele': 'il', 'Georgia': 'ge', 'Bulgaria': 'bg', 'Lussemburgo': 'lu',
    'Kosovo': 'xk', 'Kazakistan': 'kz', 'Armenia': 'am', 'Cipro': 'cy'
}

MEDIA_GOL_TORNEO = 1.35

# --- 7. TABELLA RISULTATI CON BOTTONE DI ESPORTAZIONE ---
st.header("📝 Registro Risultati Reali (Nations League)")
with st.expander("Apri il pannello per registrare i match conclusi", expanded=False):
    if not st.session_state.df_risultati.empty:
        edited_df = st.data_editor(
            st.session_state.df_risultati,
            column_config={
                "ID_Match": None,
                "Match": st.column_config.TextColumn("Incontro Programmato", disabled=True),
                "Gol Casa": st.column_config.NumberColumn("Gol Casa", min_value=0, max_value=10, step=1),
                "Gol Ospite": st.column_config.NumberColumn("Gol Ospite", min_value=0, max_value=10, step=1),
                "Giocata": st.column_config.CheckboxColumn("Partita Terminata?")
            },
            disabled=["Match", "Casa", "Ospite"],
            hide_index=True,
            key="editor_global_nations"
        )
        st.session_state.df_risultati = edited_df
        
        csv_export = edited_df[["ID_Match", "Gol Casa", "Gol Ospite", "Giocata"]].to_csv(index=False, sep=";").encode('utf-8')
        
        st.download_button(
            label="💾 CLICCA QUI PER SCARICARE I RISULTATI AGGIORNATI",
            data=csv_export,
            file_name="risultati_nations_salvati.csv",
            mime="text/csv",
            help="Scarica questo file e ricaricalo domani nella sidebar a sinistra per riprendere da dove avevi lasciato!"
        )

# --- 8. RICALCOLO DINAMICO DEL RANKING MOBILE SUI DATI CARICATI/INSERITI ---
scout_ratings = {k: v.copy() for k, v in scout_ratings_base.items()}
stats_torneo = defaultdict(lambda: {'gf': 0, 'gs': 0, 'p': 0})

for _, row in st.session_state.df_risultati.iterrows():
    if row['Giocata']:
        c, o = row['Casa'], row['Ospite']
        gc, go = int(row['Gol Casa']), int(row['Gol Ospite'])
        
        stats_torneo[c]['gf'] += gc
        stats_torneo[c]['gs'] += go
        stats_torneo[c]['p'] += 1
        
        stats_torneo[o]['gf'] += go
        stats_torneo[o]['gs'] += gc
        stats_torneo[o]['p'] += 1

for team, s in stats_torneo.items():
    if s['p'] > 0 and team in scout_ratings:
        alpha = min(s['p'] * 0.15, 0.45)
        perf_att = s['gf'] / (s['p'] * MEDIA_GOL_TORNEO)
        perf_def = s['gs'] / (s['p'] * MEDIA_GOL_TORNEO)
        
        scout_ratings[team]['attacco'] = max(0.5, (alpha * perf_att) + ((1 - alpha) * scout_ratings_base[team]['attacco']))
        scout_ratings[team]['difesa'] = max(0.3, (alpha * perf_def) + ((1 - alpha) * scout_ratings_base[team]['difesa']))

# --- 9. SIDEBAR: NAVIGAZIONE CALENDARIO ---
st.sidebar.header("🗓️ Navigazione Calendario")

if not df_calendario.empty:
    lista_opzioni = df_calendario['Etichetta_Menu'].tolist()
    match_scelto = st.sidebar.selectbox("Seleziona la partita da analizzare:", lista_opzioni)
    
    idx_selezionato = lista_opzioni.index(match_scelto)
    riga_selezionata = df_calendario.iloc[idx_selezionato]
    
    casa = riga_selezionata['Casa']
    ospite = riga_selezionata['Fuori']
    data_partita = riga_selezionata['Data']
    ora_partita = riga_selezionata['Ora']
    girone_partita = riga_selezionata['Girone']
else:
    st.sidebar.error("Impossibile generare la sidebar senza il file 'calendario_nations_league.csv'.")
    st.stop()

st.sidebar.subheader("Strategia & Infermeria")
mod_motivazione_casa = st.sidebar.slider(f"Motivazione {casa}", 0.8, 1.2, 1.0, step=0.1)
mod_motivazione_ospite = st.sidebar.slider(f"Motivazione {ospite}", 0.8, 1.2, 1.0, step=0.1)

# --- 10. GESTIONE SQUADRE PROVVISORIE (TBD) ---
fallback_profile = {'attacco': 1.00, 'difesa': 1.00, 'flag': '🏳️'}
r_casa = scout_ratings.get(casa, fallback_profile)
r_ospite = scout_ratings.get(ospite, fallback_profile)

flag_casa = r_casa.get('flag', '🏳️')
flag_ospite = r_ospite.get('flag', '🏳️')

# --- 11. CALCOLO POISSON ---
lambda_casa = MEDIA_GOL_TORNEO * (r_casa['attacco'] * mod_motivazione_casa) * r_ospite['difesa']
lambda_ospite = MEDIA_GOL_TORNEO * (r_ospite['attacco'] * mod_motivazione_ospite) * r_casa['difesa']

# --- 12. VISUALIZZAZIONE PRONOSTICO SUL MAIN PANEL ---
st.write("---")
st.subheader(f"🏟️ Pronostico: {flag_casa} {casa} vs {ospite} {flag_ospite}")

if stats_torneo[casa]['p'] > 0 or stats_torneo[ospite]['p'] > 0:
    st.info("📈 Nota dello Scout: Questo calcolo include lo stato di forma derivato dai match di Nations League registrati!")

c1, c2 = st.columns(2)
with c1: st.metric(label=f"Gol Attesi {casa} (λ)", value=f"{lambda_casa:.2f}")
with c2: st.metric(label=f"Gol Attesi {ospite} (λ)", value=f"{lambda_ospite:.2f}")

match_counts = {}
for gc in range(6):
    for go in range(6):
        prob = ((lambda_casa**gc * math.exp(-lambda_casa)) / math.factorial(gc)) * \
               ((lambda_ospite**go * math.exp(-lambda_ospite)) / math.factorial(go)) * 100
        match_counts[f"{gc} - {go}"] = prob

top_5 = sorted(match_counts.items(), key=lambda x: x[1], reverse=True)[:5]

st.divider()
colonne = st.columns(5)
for i, (res, pr) in enumerate(top_5):
    colonne[i].metric(label=f"{i+1}° Opzione", value=res, delta=f"{pr:.2f}%")

st.divider()
st.bar_chart(pd.DataFrame(top_5, columns=["Risultato", "Probabilità (%)"]), x="Risultato", y="Probabilità (%)")

# --- 13. GENERAZIONE REPORT PDF ---
st.write("---")
st.subheader("📄 Esporta Scheda Partita")

def genera_pdf():
    pdf = FPDF()
    pdf.add_page()

    pdf.set_fill_color(0, 96, 156) 
    pdf.rect(0, 0, 210, 32, 'F') 
        
    try:
        # Recupera la sigla, se non esiste nel dizionario per sicurezza la forziamo
        sigla_casa = iso_map.get(casa, 'un')
        sigla_ospite = iso_map.get(ospite, 'un')
        
        # Mappatura manuale d'emergenza in caso di dizionario non aggiornato
        if casa == "Andorra": sigla_casa = "ad"
        if ospite == "Malta": sigla_ospite = "mt"
        
        url_casa = f"https://flagcdn.com/w80/{sigla_casa}.png"
        url_ospite = f"https://flagcdn.com/w80/{sigla_ospite}.png"
        
        # Aggiungiamo l'intestazione di un browser per aggirare il blocco anti-bot (Errore 403)
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        
        # Download bandiera Casa
        req_casa = urllib.request.Request(url_casa, headers=headers)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as f_casa:
            f_casa.write(urllib.request.urlopen(req_casa).read())
            f_casa.flush()
            pdf.image(f_casa.name, 12, 9, 22)
            
        # Download bandiera Ospite
        req_ospite = urllib.request.Request(url_ospite, headers=headers)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as f_ospite:
            f_ospite.write(urllib.request.urlopen(req_ospite).read())
            f_ospite.flush()
            pdf.image(f_ospite.name, 176, 9, 22)
            
    except Exception as e:
        # Se fallisce, stampa silenziosamente senza bloccare il resto del PDF
        pass 
    
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", 'B', 18)
    pdf.cell(190, 10, "UEFA NATIONS LEAGUE - REPORT", ln=True, align='C')
    
    data_analisi = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    pdf.set_font("Arial", 'I', 10)
    pdf.cell(190, 7, f"Analisi effettuata il: {data_analisi}", ln=True, align='C')

    pdf.ln(10)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(190, 10, f"MATCH: {casa} vs {ospite}", ln=True, align='C')
    
    testo_data_ora = f"Data: {data_partita} | Ora: {ora_partita} ({girone_partita})"
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(190, 8, testo_data_ora, ln=True, align='C')
    pdf.ln(5)
    
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(190, 8, "PARAMETRI DI ANALISI APPLICATI:", ln=True)
    pdf.set_font("Arial", '', 11)
    pdf.cell(95, 8, f"Fattore Motivazione {casa}: x{mod_motivazione_casa}")
    pdf.cell(95, 8, f"Fattore Motivazione {ospite}: x{mod_motivazione_ospite}", ln=True)
    pdf.ln(5)

    pdf.set_font("Arial", 'B', 11)
    pdf.cell(190, 8, "GOL ATTESI DALLE SQUADRE:", ln=True)
    pdf.set_font("Arial", '', 11)
    pdf.cell(95, 10, f"Gol Attesi {casa}: {lambda_casa:.2f}")
    pdf.cell(95, 10, f"Gol Attesi {ospite}: {lambda_ospite:.2f}", ln=True)
    pdf.ln(10)
    
    fig, ax = plt.subplots(figsize=(4, 3))
    res_labels = [x[0] for x in top_5]
    res_probs = [x[1] for x in top_5]
    ax.bar(res_labels, res_probs, color='#00609c')
    ax.set_title('Distribuzione Risultati', fontweight='bold')
    plt.tight_layout()
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as f_chart:
        plt.savefig(f_chart.name, format="png")
        chart_path = f_chart.name
    plt.close(fig)

    pdf.set_font("Arial", 'B', 11)
    pdf.cell(190, 8, "TOP 5 RISULTATI ESATTI:", ln=True)
    
    y_start = pdf.get_y()
    
    pdf.set_font("Arial", '', 11)
    for pos, (res, pr) in enumerate(top_5, 1):
        pdf.cell(95, 10, f" {pos}. Risultato {res} -> {pr:.2f}%", ln=False)
        pdf.ln(10)
        
    pdf.image(chart_path, x=110, y=y_start, w=90)
    
    return pdf.output(dest="S").encode("latin1")

st.download_button(
    label="⬇️ Scarica PDF Partita",
    data=genera_pdf(),
    file_name=f"Pronostico_{casa}_{ospite}.pdf",
    mime="application/pdf"
)
