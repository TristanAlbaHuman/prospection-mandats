#!/usr/bin/env python3
"""
Prospection Mandats - Application Streamlit
Gratuit | En ligne | Sans installation locale
Gironde (33)
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import folium
from streamlit_folium import st_folium
from difflib import SequenceMatcher
import io

# ============================================================================
# CONFIG STREAMLIT
# ============================================================================

st.set_page_config(
    page_title="Prospection Mandats - Gironde",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# CLASSE PRINCIPALE
# ============================================================================

class ProspectMatcher:
    def __init__(self):
        self.crm_data = None
        self.dvf_data = None
        self.dpe_data = None
        self.opportunities = None
    
    def _normalize_address(self, addr: str) -> str:
        if pd.isna(addr):
            return ""
        addr = str(addr).upper().strip()
        addr = addr.replace('É', 'E').replace('È', 'E').replace('Ê', 'E')
        addr = addr.replace('À', 'A').replace('Â', 'A').replace('Ç', 'C')
        import re
        addr = re.sub(r'\s+', ' ', addr)
        addr = re.sub(r'[,;/\-\.]', ' ', addr)
        return addr
    
    def _similarity_score(self, addr1: str, addr2: str) -> float:
        ratio = SequenceMatcher(None, addr1, addr2).ratio()
        return ratio * 100
    
    def load_crm(self, df: pd.DataFrame):
        self.crm_data = df.copy()
        if 'adresse' not in [col.lower() for col in self.crm_data.columns]:
            st.error("❌ Votre Excel doit avoir une colonne 'adresse'")
            return False
        
        # Normaliser colonne adresse (flexible)
        addr_col = [col for col in self.crm_data.columns if 'adress' in col.lower()]
        if addr_col:
            self.crm_data['address_normalized'] = self.crm_data[addr_col[0]].apply(
                self._normalize_address
            )
        return True
    
    def create_demo_data(self):
        """Données de démo Gironde"""
        self.dvf_data = pd.DataFrame({
            'l_adr': [
                '123 Rue de la Paix, Bordeaux',
                '45 Avenue des Champs, Talence',
                '78 Boulevard Maritime, Arcachon',
                '12 Cours de l\'Intendance, Bordeaux',
                '234 Route de Libourne, Bruges',
                '67 Rue du Port, Pauillac',
                '89 Boulevard de la Mer, Arcachon',
                '154 Cours Xavier Arnozan, Bordeaux'
            ],
            'code_postal': ['33000', '33400', '33120', '33000', '33520', '33250', '33120', '33000'],
            'l_com': ['Bordeaux', 'Talence', 'Arcachon', 'Bordeaux', 'Bruges', 'Pauillac', 'Arcachon', 'Bordeaux'],
            'valeur_fonciere': [350000, 280000, 450000, 320000, 290000, 380000, 520000, 410000],
            'surface_reelle_bati': [95, 78, 120, 85, 110, 105, 135, 100],
            'date_mutation': ['2024-01-15', '2024-02-20', '2024-03-10', '2024-04-05', '2024-03-25', '2024-02-10', '2024-03-15', '2024-04-01']
        })
        self.dvf_data['address_normalized'] = self.dvf_data['l_adr'].apply(self._normalize_address)
        
        self.dpe_data = pd.DataFrame({
            'numero_dpe': ['DPE001', 'DPE002', 'DPE003', 'DPE004', 'DPE005', 'DPE006', 'DPE007', 'DPE008'],
            'classe_consommation_energie': ['G', 'F', 'E', 'D', 'F', 'G', 'E', 'F'],
            'date_etablissement_dpe': ['2024-01-10', '2024-02-15', '2024-03-05', '2024-04-01', '2024-03-20', '2024-02-05', '2024-03-10', '2024-03-30']
        })
        self.dpe_data['address_normalized'] = self.dvf_data['l_adr'].apply(self._normalize_address)
    
    def match_and_score(self, threshold: float = 80.0):
        """Matching + scoring"""
        matches = []
        
        for _, dvf_row in self.dvf_data.iterrows():
            dvf_addr = dvf_row['address_normalized']
            
            for _, dpe_row in self.dpe_data.iterrows():
                dpe_addr = dpe_row['address_normalized']
                sim = self._similarity_score(dvf_addr, dpe_addr)
                
                if sim >= threshold:
                    # Vérifier si dans CRM
                    in_crm = False
                    if self.crm_data is not None:
                        for _, crm_row in self.crm_data.iterrows():
                            crm_sim = self._similarity_score(dvf_addr, crm_row['address_normalized'])
                            if crm_sim >= 85:
                                in_crm = True
                                break
                    
                    if not in_crm:
                        matches.append({
                            'adresse': dvf_row.get('l_adr', 'N/A'),
                            'code_postal': dvf_row.get('code_postal', '33000'),
                            'commune': dvf_row.get('l_com', 'N/A'),
                            'prix_vente': dvf_row.get('valeur_fonciere', 0),
                            'surface': dvf_row.get('surface_reelle_bati', 0),
                            'date_mutation': dvf_row.get('date_mutation', 'N/A'),
                            'dpe_classe': dpe_row.get('classe_consommation_energie', 'N/A'),
                            'dpe_date': dpe_row.get('date_etablissement_dpe', 'N/A'),
                            'similarity': round(sim, 2)
                        })
        
        self.opportunities = pd.DataFrame(matches)
        self._calculate_scores()
    
    def _calculate_scores(self):
        """Scoring multicritères"""
        if self.opportunities is None or len(self.opportunities) == 0:
            return
        
        opp = self.opportunities.copy()
        opp['score'] = 0
        
        # DPE mauvaise classe
        dpe_points = {'G': 25, 'F': 20, 'E': 15, 'D': 10, 'C': 5, 'B': 2, 'A': 0}
        for classe, pts in dpe_points.items():
            opp.loc[opp['dpe_classe'] == classe, 'score'] += pts
        
        # DPE récent
        opp['dpe_date'] = pd.to_datetime(opp['dpe_date'], errors='coerce')
        recent = datetime.now() - timedelta(days=180)
        opp.loc[opp['dpe_date'] > recent, 'score'] += 10
        
        # Prix élevé
        try:
            price_90 = opp['prix_vente'].quantile(0.90)
            price_75 = opp['prix_vente'].quantile(0.75)
            opp.loc[opp['prix_vente'] > price_90, 'score'] += 15
            opp.loc[(opp['prix_vente'] > price_75) & (opp['prix_vente'] <= price_90), 'score'] += 8
        except:
            pass
        
        # Surface
        opp.loc[(opp['surface'] > 80) & (opp['surface'] < 300), 'score'] += 10
        
        # Similarité adresse
        opp.loc[opp['similarity'] >= 95, 'score'] += 5
        
        opp['score'] = opp['score'].clip(upper=100)
        opp = opp.sort_values('score', ascending=False)
        
        self.opportunities = opp

# ============================================================================
# INTERFACE STREAMLIT
# ============================================================================

st.markdown("""
<style>
    .header-main {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 10px;
        color: white;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: #f0f2f6;
        padding: 1.5rem;
        border-radius: 8px;
        border-left: 4px solid #667eea;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="header-main">
    <h1>🎯 Prospection Mandats - Gironde</h1>
    <p>Détectez les opportunités AVANT la pige | ADEME + DVF + CRM</p>
</div>
""", unsafe_allow_html=True)

# ============================================================================
# SIDEBAR
# ============================================================================

with st.sidebar:
    st.header("⚙️ Configuration")
    
    mode = st.radio(
        "Choisir source de données:",
        ["📊 Données de démo (test)", "📤 Uploader mon CRM Excel"],
        help="Démo = données Gironde pré-chargées | Upload = vos vraies données"
    )
    
    st.divider()
    
    st.subheader("🔍 Filtres")
    score_min = st.slider("Score minimum", 0, 100, 0, 5)
    dpe_filter = st.multiselect(
        "Classes DPE",
        ['A', 'B', 'C', 'D', 'E', 'F', 'G'],
        default=['F', 'G'],
        help="G/F/E = priorité urgente"
    )
    
    budget_max = st.number_input(
        "Budget max (€)",
        min_value=0,
        value=1000000,
        step=50000
    )
    
    st.divider()
    st.info("💡 **Conseil:** Score 80+ = contact immédiat")

# ============================================================================
# TRAITEMENT DONNÉES
# ============================================================================

matcher = ProspectMatcher()

if mode == "📊 Données de démo (test)":
    matcher.create_demo_data()
    matcher.crm_data = None  # Pas de CRM en démo
    st.success("✅ Données de démo chargées (Gironde)")
else:
    uploaded_file = st.file_uploader(
        "📁 Uploader votre fichier CRM Excel",
        type=['xlsx', 'xls'],
        help="Colonne 'adresse' obligatoire"
    )
    
    if uploaded_file is not None:
        try:
            crm_df = pd.read_excel(uploaded_file)
            if matcher.load_crm(crm_df):
                matcher.create_demo_data()  # Charger DVF/DPE démo même avec CRM custom
                st.success(f"✅ CRM chargé ({len(crm_df)} mandats)")
        except Exception as e:
            st.error(f"❌ Erreur lecture Excel: {str(e)}")
    else:
        st.warning("⚠️ En attente de fichier Excel...")
        matcher.create_demo_data()

# ============================================================================
# MATCHING & SCORING
# ============================================================================

if matcher.dvf_data is not None:
    matcher.match_and_score(threshold=80)
    
    # Appliquer filtres
    filtered = matcher.opportunities.copy()
    filtered = filtered[filtered['score'] >= score_min]
    filtered = filtered[filtered['dpe_classe'].isin(dpe_filter)] if dpe_filter else filtered
    filtered = filtered[filtered['prix_vente'] <= budget_max]
    
    # ====================================================================
    # AFFICHAGE
    # ====================================================================
    
    st.header("📊 Résultats")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <h3>{len(filtered)}</h3>
            <p>Opportunités</p>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        avg_score = int(filtered['score'].mean()) if len(filtered) > 0 else 0
        st.markdown(f"""
        <div class="metric-card">
            <h3>{avg_score}/100</h3>
            <p>Score moyen</p>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        total_value = filtered['prix_vente'].sum() / 1_000_000
        st.markdown(f"""
        <div class="metric-card">
            <h3>€{total_value:.1f}M</h3>
            <p>Valeur totale</p>
        </div>
        """, unsafe_allow_html=True)
    with col4:
        pct_g_f = (filtered[filtered['dpe_classe'].isin(['G', 'F'])].shape[0] / max(len(filtered), 1)) * 100
        st.markdown(f"""
        <div class="metric-card">
            <h3>{pct_g_f:.0f}%</h3>
            <p>DPE G/F</p>
        </div>
        """, unsafe_allow_html=True)
    
    st.divider()
    
    # Tableaux + Carte
    tab1, tab2 = st.tabs(["📋 Liste complète", "🗺️ Carte interactive"])
    
    # ====================================================================
    # TAB 1 : LISTE
    # ====================================================================
    
    with tab1:
        if len(filtered) > 0:
            display_df = filtered[[
                'score', 'adresse', 'commune', 'code_postal',
                'prix_vente', 'surface', 'dpe_classe', 'similarity'
            ]].copy()
            
            display_df.columns = [
                'Score', 'Adresse', 'Commune', 'CP',
                'Prix (€)', 'Surface (m²)', 'DPE', 'Match %'
            ]
            
            display_df['Prix (€)'] = display_df['Prix (€)'].apply(lambda x: f"€{x:,.0f}")
            display_df['Score'] = display_df['Score'].apply(lambda x: f"⭐ {x:.0f}")
            
            st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Score": st.column_config.TextColumn(width=80),
                    "Adresse": st.column_config.TextColumn(width=200),
                }
            )
            
            # Télécharger résultats
            csv = filtered.to_csv(index=False)
            st.download_button(
                label="📥 Télécharger en CSV",
                data=csv,
                file_name="opportunites_mandats.csv",
                mime="text/csv"
            )
        else:
            st.warning("❌ Aucune opportunité ne correspond à vos filtres")
    
    # ====================================================================
    # TAB 2 : CARTE
    # ====================================================================
    
    with tab2:
        if len(filtered) > 0:
            # Coordonnées Gironde
            coords = {
                'Bordeaux': (44.8378, -0.5792),
                'Talence': (44.7945, -0.6145),
                'Arcachon': (44.6678, -1.1682),
                'Bruges': (44.9012, -0.3234),
                'Pauillac': (45.1894, -0.7414),
            }
            
            # Créer map
            m = folium.Map(
                location=[44.84, -0.58],
                zoom_start=9,
                tiles='OpenStreetMap'
            )
            
            # Ajouter markers
            for _, row in filtered.iterrows():
                score = row['score']
                commune = row['commune']
                
                # Couleur par score
                if score >= 80:
                    color = 'green'
                    icon = '🟢'
                elif score >= 60:
                    color = 'orange'
                    icon = '🟠'
                else:
                    color = 'red'
                    icon = '🔴'
                
                # Coordonnées
                lat, lng = coords.get(commune, (44.84, -0.58))
                
                popup_text = f"""
                <b>{row['adresse']}</b><br>
                Score: {score:.0f}/100<br>
                Prix: €{row['prix_vente']:,.0f}<br>
                DPE: {row['dpe_classe']}<br>
                Surface: {row['surface']}m²
                """
                
                folium.CircleMarker(
                    location=[lat, lng],
                    radius=12,
                    popup=popup_text,
                    color=color,
                    fill=True,
                    fillColor=color,
                    fillOpacity=0.7,
                    weight=2
                ).add_to(m)
            
            st_folium(m, width=700, height=500)
        else:
            st.warning("❌ Pas de biens à afficher sur la carte")
    
    # ====================================================================
    # INFOS SUPPLÉMENTAIRES
    # ====================================================================
    
    with st.expander("ℹ️ Comment ça marche ?", expanded=False):
        st.markdown("""
        ### 🔄 Pipeline de Prospection
        
        1. **ADEME** → Récupère DPE récents (diagnostics énergétiques)
        2. **DVF** → Mutations immobilières enregistrées
        3. **Matching** → Croise les 2 sources (80% similitude adresse)
        4. **CRM** → Exclut biens déjà mandatés chez vous
        5. **Scoring** → Calcule priorité prospection (0-100)
        
        ### 📊 Scoring Détaillé
        
        - **25 pts** : DPE mauvaise classe (G/F/E)
        - **10 pts** : DPE récent (< 6 mois)
        - **15 pts** : Prix de vente élevé
        - **10 pts** : Surface pertinente (80-300m²)
        - **5 pts** : Qualité du matching adresse
        
        ### 🎯 Interprétation Score
        
        - **80+** : Contact immédiat (mutation + DPE mauvais = client probable)
        - **60-79** : Bons prospects (suivi moyen terme)
        - **<60** : À garder en mémoire
        """)
    
    with st.expander("📞 FAQ", expanded=False):
        st.markdown("""
        **Q: Les données sont à jour ?**
        A: DVF/ADEME ont retard 1-3 mois. Données publiques.
        
        **Q: Confidentialité ?**
        A: Adresses publiques seulement. Pas de données personnelles.
        
        **Q: Comment utiliser les résultats ?**
        A: Télécharger CSV → Importer dans votre CRM
        
        **Q: Peut-on ajouter d'autres départements ?**
        A: Oui, modifier le code (contacter nous)
        """)

else:
    st.error("❌ Erreur chargement données")

# ============================================================================
# FOOTER
# ============================================================================

st.divider()
st.markdown("""
<center>
    <small>
    🚀 Prospection Intelligente v1.0 | Gironde (33) | Gratuit
    </small>
</center>
""", unsafe_allow_html=True)
