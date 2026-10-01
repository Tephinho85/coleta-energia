# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime
import plotly.express as px
import io
import base64
import urllib.parse

st.set_page_config(
    page_title="Dashboard de Eficiência Energética",
    page_icon="⚡",
    layout="wide"
)

# Injeção de CSS focada EXCLUSIVAMENTE nos campos de texto específicos
st.markdown("""
    <style>
        input[aria-label="Utilizador:"] { text-transform: uppercase !important; }
        input[aria-label="Nome do Utilizador:"] { text-transform: uppercase !important; }
        input[aria-label="Nome do Setor:"] { text-transform: uppercase !important; }
        input[aria-label="Nome e Unidade (ex: GÁS GLP (KG)):"] { text-transform: uppercase !important; }
    </style>
""", unsafe_allow_html=True)

# Configuração Otimizada da Conexão PostgreSQL com Connection Pooling
try:
    db_config = st.secrets["postgres"]
    
    # Codifica a password para lidar com caracteres especiais como o @
    senha_segura = urllib.parse.quote_plus(db_config['password'])
    
    DATABASE_URL = f"postgresql+psycopg2://{db_config['user']}:{senha_segura}@{db_config['host']}:{db_config['port']}/{db_config['database']}"
    
    # Motor otimizado com pool de conexões ativas para alta performance
    engine = create_engine(
        DATABASE_URL,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=3600
    )
except Exception as e:
    st.error(f"Erro ao configurar os segredos do PostgreSQL: {e}")
    st.stop()

# -----------------------------------------------------------------------------
# 1. Configuração da Base de Dados (PostgreSQL)
# -----------------------------------------------------------------------------
def preparar_banco():
    with engine.begin() as conn:
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS LEITURAS_CONSUMO (
            ID SERIAL PRIMARY KEY,
            DATA_LEITURA TEXT,
            UNIDADE TEXT,
            SETOR TEXT,
            TIPO_CONSUMO TEXT,
            LEITURA DOUBLE PRECISION,
            PRODUCAO_TON DOUBLE PRECISION,
            COLABORADOR TEXT,
            DATA_REGISTO TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOTO_EVIDENCIA TEXT
        )
        """))
        
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS SETORES (
            ID SERIAL PRIMARY KEY,
            NOME TEXT UNIQUE
        )
        """))
        
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS TIPOS_CONSUMO (
            ID SERIAL PRIMARY KEY,
            NOME TEXT UNIQUE
        )
        """))

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS USUARIOS (
            ID SERIAL PRIMARY KEY,
            NOME TEXT UNIQUE,
            SENHA TEXT
        )
        """))
        
        # Dados padrão de setores
        res_setores = conn.execute(text("SELECT COUNT(*) FROM SETORES")).scalar()
        if res_setores == 0:
            for setor in ["INDÚSTRIA", "LAVANDERIA", "CALDEIRA"]:
                conn.execute(text("INSERT INTO SETORES (NOME) VALUES (:nome) ON CONFLICT (NOME) DO NOTHING"), {"nome": setor})
            
        # Dados padrão de tipos de consumo
        res_tipos = conn.execute(text("SELECT COUNT(*) FROM TIPOS_CONSUMO")).scalar()
        if res_tipos == 0:
            for tipo in ["ENERGIA ELÉTRICA (KWH)", "VAPOR (KG)", "ÁGUA (M3)"]:
                conn.execute(text("INSERT INTO TIPOS_CONSUMO (NOME) VALUES (:nome) ON CONFLICT (NOME) DO NOTHING"), {"nome": tipo})

        # Utilizadores padrão iniciais
        res_users = conn.execute(text("SELECT COUNT(*) FROM USUARIOS")).scalar()
        if res_users == 0:
            conn.execute(text("INSERT INTO USUARIOS (NOME, SENHA) VALUES (:nome, :senha) ON CONFLICT (NOME) DO NOTHING"), {"nome": "TEPHINHO", "senha": "1234"})
            conn.execute(text("INSERT INTO USUARIOS (NOME, SENHA) VALUES (:nome, :senha) ON CONFLICT (NOME) DO NOTHING"), {"nome": "ADM", "senha": "Frisa@59"})

preparar_banco()

# -----------------------------------------------------------------------------
# 2. Gestão de Sessão e Ecrã de Login
# -----------------------------------------------------------------------------
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
    st.session_state.usuario_atual = ""

if not st.session_state.autenticado:
    st.title("🔐 Acesso Restrito - Coleta de Consumo")
    st.markdown("Por favor, efetue o login com as suas credenciais para aceder ao sistema.")
    
    with st.form("form_login"):
        user_input = st.text_input("Utilizador:")
        pass_input = st.text_input("Palavra-passe:", type="password")
        btn_entrar = st.form_submit_button("Entrar no Sistema")
        
        if btn_entrar:
            user_limpo = user_input.strip()
            try:
                with engine.connect() as conn:
                    query = text("SELECT NOME FROM USUARIOS WHERE UPPER(NOME) = UPPER(:user) AND SENHA = :senha")
                    resultado = conn.execute(query, {"user": user_limpo, "senha": pass_input}).fetchone()
                    
                    if resultado:
                        st.session_state.autenticado = True
                        st.session_state.usuario_atual = resultado[0].upper()
                        st.success("Autenticação bem-sucedida!")
                        st.rerun()
                    else:
                        st.error("Utilizador ou palavra-passe incorretos.")
            except Exception as e:
                st.error(f"Erro na autenticação: {e}")
    st.stop()

# -----------------------------------------------------------------------------
# Funções de Apoio
# -----------------------------------------------------------------------------
def obter_lista_setores():
    try:
        df = pd.read_sql("SELECT NOME FROM SETORES ORDER BY NOME", con=engine)
        df.columns = df.columns.str.upper()
        return df["NOME"].tolist()
    except Exception:
        return ["ERRO AO CARREGAR SETORES"]

def obter_lista_tipos():
    try:
        df = pd.read_sql("SELECT NOME FROM TIPOS_CONSUMO ORDER BY NOME", con=engine)
        df.columns = df.columns.str.upper()
        return df["NOME"].tolist()
    except Exception:
        return ["ERRO AO CARREGAR TIPOS"]

def carregar_utilizadores():
    try:
        df = pd.read_sql("SELECT ID, NOME FROM USUARIOS", con=engine)
        df.columns = df.columns.str.upper()
        return df
    except Exception:
        return pd.DataFrame()

# -----------------------------------------------------------------------------
# 3. Barra Lateral: Utilizador, Cadastros e Painel Admin
# -----------------------------------------------------------------------------
st.sidebar.title(f"👤 Olá, {st.session_state.usuario_atual}")
if st.sidebar.button("Terminar Sessão"):
    st.session_state.autenticado = False
    st.session_state.usuario_atual = ""
    st.rerun()

st.sidebar.divider()
st.sidebar.title("⚙️ Cadastros e Administração")

with st.sidebar.expander("👥 Gerir Utilizadores"):
    st.markdown("**Cadastrar Novo Operador**")
    with st.form("form_novo_usuario", clear_on_submit=True):
        novo_user = st.text_input("Nome do Utilizador:")
        nova_senha = st.text_input("Palavra-passe:", type="password")
        if st.form_submit_button("Criar Utilizador"):
            if novo_user.strip() and nova_senha.strip():
                user_novo_formatado = novo_user.strip().upper()
                try:
                    with engine.begin() as conn:
                        conn.execute(
                            text("INSERT INTO USUARIOS (NOME, SENHA) VALUES (:nome, :senha)"),
                            {"nome": user_novo_formatado, "senha": nova_senha}
                        )
                    st.success(f"Utilizador '{user_novo_formatado}' criado!")
                    st.rerun()
                except Exception:
                    st.error("Este utilizador já existe ou ocorreu um erro.")
            else:
                st.warning("Preencha todos os campos.")
                
    st.markdown("---")
    st.markdown("**Remover Utilizador**")
    df_users = carregar_utilizadores()
    if not df_users.empty:
        user_para_apagar = st.selectbox("Selecione o utilizador:", options=df_users["NOME"].tolist(), key="del_user_select")
        if st.button("🗑️ Eliminar Utilizador", type="primary"):
            if user_para_apagar in ["TEPHINHO", "ADM"] and st.session_state.usuario_atual != user_para_apagar:
                st.error("Não pode apagar utilizadores mestres principais.")
            else:
                try:
                    with engine.begin() as conn:
                        conn.execute(text("DELETE FROM USUARIOS WHERE NOME = :nome"), {"nome": user_para_apagar})
                    st.success(f"Utilizador '{user_para_apagar}' eliminado!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao eliminar: {e}")

with st.sidebar.expander("Adicionar Novo Setor"):
    with st.form("form_novo_setor", clear_on_submit=True):
        novo_setor = st.text_input("Nome do Setor:")
        if st.form_submit_button("Gravar Setor"):
            if novo_setor.strip():
                setor_formatado = novo_setor.strip().upper()
                try:
                    with engine.begin() as conn:
                        conn.execute(text("INSERT INTO SETORES (NOME) VALUES (:nome)"), {"nome": setor_formatado})
                    st.sidebar.success(f"Setor '{setor_formatado}' adicionado!")
                    st.rerun()
                except Exception:
                    st.sidebar.error("Este setor já existe.")
            else:
                st.sidebar.warning("Digite um nome válido.")

with st.sidebar.expander("Adicionar Tipo de Consumo"):
    with st.form("form_novo_tipo", clear_on_submit=True):
        novo_tipo = st.text_input("Nome e Unidade (ex: GÁS GLP (KG)):")
        if st.form_submit_button("Gravar Tipo"):
            if novo_tipo.strip():
                tipo_formatado = novo_tipo.strip().upper()
                try:
                    with engine.begin() as conn:
                        conn.execute(text("INSERT INTO TIPOS_CONSUMO (NOME) VALUES (:nome)"), {"nome": tipo_formatado})
                    st.sidebar.success(f"Tipo '{tipo_formatado}' adicionado!")
                    st.rerun()
                except Exception:
                    st.sidebar.error("Este tipo já existe.")
            else:
                st.sidebar.warning("Digite um nome válido.")

# -----------------------------------------------------------------------------
# 4. Formulário de Coleta em Campo
# -----------------------------------------------------------------------------
st.sidebar.title("📋 Nova Leitura")

lista_setores_atualizada = obter_lista_setores()
lista_tipos_atualizada = obter_lista_tipos()

with st.sidebar.form("form_coleta", clear_on_submit=True):
    unidade = st.selectbox("Unidade:", ["UNIDADE 1", "UNIDADE 2", "UNIDADE 3"])
    tipo = st.selectbox("Tipo de Consumo:", lista_tipos_atualizada)
    setor = st.selectbox("Setor (Medidor):", lista_setores_atualizada)
    
    leitura = st.number_input("Valor da Leitura:", min_value=0.0, format="%.2f")
    producao = st.number_input("Volume de Produção (Ton/Kg):", min_value=0.0, format="%.2f")
    
    colaborador = st.session_state.usuario_atual
    data_leitura = st.date_input("Data Referência da Leitura:")
    
    foto_medidor = st.camera_input("📸 Foto do Medidor (Opcional)")
    
    submetido = st.form_submit_button("Guardar Leitura")

if submetido:
    foto_b64 = None
    if foto_medidor is not None:
        bytes_foto = foto_medidor.getvalue()
        foto_b64 = base64.b64encode(bytes_foto).decode('utf-8')

    try:
        with engine.begin() as conn:
            query_insercao = text("""
                INSERT INTO LEITURAS_CONSUMO 
                (DATA_LEITURA, UNIDADE, SETOR, TIPO_CONSUMO, LEITURA, PRODUCAO_TON, COLABORADOR, FOTO_EVIDENCIA)
                VALUES (:d, :u, :s, :t, :l, :p, :c, :f)
            """)
            conn.execute(query_insercao, {
                "d": str(data_leitura),
                "u": unidade,
                "s": setor,
                "t": tipo,
                "l": leitura,
                "p": producao,
                "c": colaborador,
                "f": foto_b64
            })
        st.sidebar.success("Leitura guardada com sucesso!")
        st.rerun()
    except Exception as e:
        st.sidebar.error(f"Erro ao guardar: {e}")

# -----------------------------------------------------------------------------
# 5. Dashboard Principal e Abas
# -----------------------------------------------------------------------------
def carregar_dados_reais():
    try:
        df = pd.read_sql("SELECT * FROM LEITURAS_CONSUMO", con=engine)
        df.columns = df.columns.str.upper()
        return df
    except Exception:
        return pd.DataFrame()

df_bruto = carregar_dados_reais()

st.title("⚡ Dashboard Gerencial (Cloud Mode)")

if not df_bruto.empty:
    df_dashboard = df_bruto.copy()
    df_dashboard["DATA_LEITURA"] = pd.to_datetime(df_dashboard["DATA_LEITURA"])
    df_dashboard["Consumo_por_Ton"] = df_dashboard["LEITURA"] / df_dashboard["PRODUCAO_TON"].replace(0, 1)

    aba_geral, aba_graficos, aba_gestao = st.tabs(["📊 Visão Geral", "📈 Análises Gráficas", "🛠 Gestão de Registros"])

    with aba_geral:
        total_leitura = df_dashboard["LEITURA"].sum()
        total_producao = df_dashboard["PRODUCAO_TON"].sum()
        indicador = total_leitura / total_producao if total_producao > 0 else 0

        col1, col2, col3 = st.columns(3)
        col1.metric("Consumo Acumulado", f"{total_leitalec:,.0f}" if 'total_leitalec' in locals() else f"{total_leitura:,.0f}")
        col2.metric("Produção Acumulada", f"{total_producao:,.0f}")
        col3.metric("Eficiência Geral (Consumo/Ton)", f"{indicador:,.2f}")

        st.divider()
        st.subheader("Base Analítica para Integração de Custos")
        
        df_rateio = df_dashboard.groupby(["UNIDADE", "SETOR", "TIPO_CONSUMO"]).agg(
            Consumo_Total=("LEITURA", "sum"),
            Producao_Total=("PRODUCAO_TON", "sum")
        ).reset_index()
        df_rateio["Indicador (Consumo/Ton)"] = df_rateio["Consumo_Total"] / df_rateio["Producao_Total"].replace(0, 1)
        
        st.dataframe(df_rateio, use_container_width=True)

        buffer_excel = io.BytesIO()
        with pd.ExcelWriter(buffer_excel, engine='openpyxl') as writer:
            df_rateio.to_excel(writer, index=False, sheet_name='Base_Rateio')

        st.download_button(
            label="📥 Exportar Base Analítica para Excel",
            data=buffer_excel.getvalue(),
            file_name=f"Base_Analitica_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary"
        )

    with aba_graficos:
        st.subheader("Evolução Temporal e Comparativos")
        tipo_grafico = st.selectbox("Selecione o Tipo de Consumo:", options=df_dashboard["TIPO_CONSUMO"].unique())
        df_graficos = df_dashboard[df_dashboard["TIPO_CONSUMO"] == tipo_grafico]

        if not df_graficos.empty:
            col_graf1, col_graf2 = st.columns(2)

            with col_graf1:
                df_temporal = df_graficos.groupby("DATA_LEITURA")[["LEITURA"]].sum().reset_index().sort_values("DATA_LEITURA")
                fig_linha = px.line(df_temporal, x="DATA_LEITURA", y="LEITURA", markers=True, title=f"Evolução - {tipo_grafico}")
                st.plotly_chart(fig_linha, use_container_width=True)

            with col_graf2:
                df_setor = df_graficos.groupby(["UNIDADE", "SETOR"])[["LEITURA"]].sum().reset_index()
                fig_barra = px.bar(df_setor, x="SETOR", y="LEITURA", color="UNIDADE", barmode="group", title=f"Comparativo - {tipo_grafico}")
                st.plotly_chart(fig_barra, use_container_width=True)
        else:
            st.warning("Sem dados suficientes para este tipo de consumo.")

    with aba_gestao:
        st.subheader("Gestão de Registros (Editar / Eliminar)")
        colunas_exibicao = ["ID", "DATA_LEITURA", "UNIDADE", "SETOR", "TIPO_CONSUMO", "LEITURA", "PRODUCAO_TON", "COLABORADOR"]
        st.dataframe(df_bruto[colunas_exibicao], use_container_width=True)
        
        id_alvo = st.selectbox("Selecione o ID do registro a modificar ou visualizar:", options=[""] + df_bruto["ID"].astype(str).tolist())
        
        if id_alvo:
            registo_selecionado = df_bruto[df_bruto["ID"].astype(str) == id_alvo].iloc[0]
            col_edit, col_del, col_foto = st.columns([1, 1, 1])
            
            with col_edit:
                with st.form("form_edicao"):
                    st.info(f"ID: {id_alvo} | Colaborador: {registo_selecionado['COLABORADOR']}")
                    nova_leitura = st.number_input("Corrigir Leitura:", value=float(registo_selecionado["LEITURA"]), format="%.2f")
                    nova_producao = st.number_input("Corrigir Produção:", value=float(registo_selecionado["PRODUCAO_TON"]), format="%.2f")
                    
                    if st.form_submit_button("Atualizar Registro"):
                        try:
                            with engine.begin() as conn:
                                conn.execute(
                                    text("UPDATE LEITURAS_CONSUMO SET LEITURA = :l, PRODUCAO_TON = :p WHERE ID = :id"),
                                    {"l": nova_leitura, "p": nova_producao, "id": int(id_alvo)}
                                )
                            st.success("Atualizado com sucesso!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro: {e}")
            
            with col_del:
                st.warning("Ação irreversível.")
                if st.button("🗑️ Eliminar Registro", type="primary"):
                    try:
                        with engine.begin() as conn:
                            conn.execute(text("DELETE FROM LEITURAS_CONSUMO WHERE ID = :id"), {"id": int(id_alvo)})
                        st.success("Eliminado com sucesso!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro: {e}")
            
            with col_foto:
                st.markdown("**Evidência Fotográfica:**")
                if "FOTO_EVIDENCIA" in registo_selecionado and pd.notna(registo_selecionado["FOTO_EVIDENCIA"]):
                    imagem_bytes = base64.b64decode(registo_selecionado["FOTO_EVIDENCIA"])
                    st.image(imagem_bytes, caption=f"Foto do Medidor (ID: {id_alvo})", use_column_width=True)
                else:
                    st.info("Nenhuma fotografia anexada a este registo.")
else:
    st.info("Nenhuma leitura registrada na base de dados na nuvem ainda. Utilize o menu lateral para iniciar.")