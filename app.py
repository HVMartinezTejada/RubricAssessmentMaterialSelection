import streamlit as st
import pandas as pd
import json
from datetime import datetime, timedelta
from collections import Counter
import time

# Configuración inicial de la página
st.set_page_config(
    page_title="Sistema de Evaluación por Rúbrica. Created by HV Martínez-Tejada",
    page_icon="📊",
    layout="wide"
)

# ============================================
# 1. SISTEMA DE PERSISTENCIA DE DATOS
# ============================================

def cargar_datos():
    """Cargar datos desde archivos JSON"""
    try:
        with open('calificaciones.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"calificaciones": [], "sesiones": []}

def guardar_datos(datos):
    """Guardar datos en archivo JSON"""
    with open('calificaciones.json', 'w', encoding='utf-8') as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)

def cargar_configuracion():
    """Cargar configuración de la rúbrica"""
    try:
        with open('configuracion_rubrica.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        # Configuración por defecto
        config = {
            "descriptores": {
                "C111": {
                    "A": "Realiza una identificación exhaustiva y holística...",
                    "B": "Identifica de manera exhaustiva requisitos técnicos...",
                    "C": "Identifica correctamente los requisitos técnicos...",
                    "D": "Identifica sólo los requisitos técnicos más obvios...",
                    "E": "Omite requisitos técnicos clave..."
                },
                # ... (se completará con todos los descriptores)
            },
            "pesos": {
                "ID11": 25,
                "ID12": 25,
                "ID13": 50
            }
        }
        return config

def guardar_configuracion(config):
    """Guardar configuración de la rúbrica"""
    with open('configuracion_rubrica.json', 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

# ============================================
# 2. INICIALIZACIÓN DEL ESTADO DE LA SESIÓN
# ============================================

if 'datos' not in st.session_state:
    st.session_state.datos = cargar_datos()

if 'config' not in st.session_state:
    st.session_state.config = cargar_configuracion()

if 'sesion_activa' not in st.session_state:
    st.session_state.sesion_activa = False

if 'tiempo_fin' not in st.session_state:
    st.session_state.tiempo_fin = None

if 'grupos_calificando' not in st.session_state:
    st.session_state.grupos_calificando = {}

# ============================================
# 3. DEFINICIÓN DE ESTRUCTURAS DE DATOS
# ============================================

# Estructura completa de la rúbrica
RUBRICA_ESTRUCTURA = {
    "ID11: IDENTIFICAR": {
        "C111": ["C1111", "C1112", "C1113", "C1114", "C1115"],
        "C112": ["C1116", "C1117", "C1118", "C1119", "C11110"]
    },
    "ID12: FORMULAR": {
        "C121": ["C1211", "C1212", "C1213", "C1214", "C1215"],
        "C122": ["C1226", "C1227", "C1228", "C1229", "C12210"]
    },
    "ID13: RESOLVER": {
        "C131": ["C1311", "C1312", "C1313", "C1314", "C1315"],
        "C132": ["C1316", "C1317", "C1318", "C1319", "C13110"],
        "C133": ["C13111", "C13112", "C13113", "C13114", "C13115"]
    }
}

# Mapeo de códigos a descriptores (ejemplo para C111)
DESCRIPTORES_EJEMPLO = {
    "C111": {
        "A": "Realiza una identificación exhaustiva y holística. Anticipa riesgos o conexiones no obvias entre los requisitos técnicos y las complejidades de la cadena de suministro global.",
        "B": "Identifica de manera exhaustiva requisitos técnicos y vincula explícitamente varios factores de riesgo del documento (geopolíticos, ambientales, éticos) al contexto específico del caso.",
        "C": "Identifica correctamente los requisitos técnicos primarios y secundarios. Menciona al menos un concepto del documento (ej: 'material crítico', 'riesgo regulatorio') aplicado al caso.",
        "D": "Identifica sólo los requisitos técnicos más obvios. Menciona aspectos de suministro de forma superficial y desconectada.",
        "E": "Omite requisitos técnicos clave y no considera aspectos de suministro o sostenibilidad."
    }
}

# Rango de calificaciones numéricas
RANGOS_NUMERICOS = {
    "A": (4.5, 5.0),
    "B": (4.0, 4.5),
    "C": (3.5, 4.0),
    "D": (3.0, 3.5),
    "E": (0.0, 3.0)
}

# ============================================
# 4. FUNCIONES DE CÁLCULO
# ============================================

def calcular_moda(calificaciones):
    """Calcular la moda (valor más frecuente) de una lista"""
    if not calificaciones:
        return None
    conteo = Counter(calificaciones)
    return conteo.most_common(1)[0][0]

def letra_a_numero(letra):
    """Convertir letra de calificación a valor numérico central"""
    if letra not in RANGOS_NUMERICOS:
        return 0.0
    min_val, max_val = RANGOS_NUMERICOS[letra]
    return (min_val + max_val) / 2

def calcular_promedios_grupo(grupo_id):
    """Calcular promedios para un grupo específico"""
    # Filtrar calificaciones del grupo
    calificaciones_grupo = [
        cal for cal in st.session_state.datos["calificaciones"]
        if cal["grupo"] == grupo_id
    ]
    
    if not calificaciones_grupo:
        return None
    
    # Estructura para resultados
    resultados = {
        "grupo": grupo_id,
        "criterios": {},
        "ids": {},
        "final": 0.0
    }
    
    # Calcular moda por criterio
    for id_nombre, criterios in RUBRICA_ESTRUCTURA.items():
        for criterio, _ in criterios.items():
            califs_criterio = [
                cal["calificaciones"].get(criterio)
                for cal in calificaciones_grupo
                if criterio in cal["calificaciones"]
            ]
            
            # Filtrar valores None
            califs_criterio = [c for c in califs_criterio if c is not None]
            
            if califs_criterio:
                moda = calcular_moda(califs_criterio)
                resultados["criterios"][criterio] = {
                    "cualitativa": moda,
                    "numerica": letra_a_numero(moda),
                    "total_calificaciones": len(califs_criterio)
                }
    
    # Calcular promedio por ID
    for id_nombre, criterios in RUBRICA_ESTRUCTURA.items():
        valores_criterios = []
        for criterio in criterios.keys():
            if criterio in resultados["criterios"]:
                valores_criterios.append(resultados["criterios"][criterio]["numerica"])
        
        if valores_criterios:
            resultados["ids"][id_nombre] = {
                "promedio": sum(valores_criterios) / len(valores_criterios)
            }
    
    # Calcular nota final ponderada
    pesos = st.session_state.config["pesos"]
    nota_final = 0.0
    
    # Mapear nombres de ID a claves de pesos
    id_to_peso_key = {
        "ID11: IDENTIFICAR": "ID11",
        "ID12: FORMULAR": "ID12",
        "ID13: RESOLVER": "ID13"
    }
    
    for id_nombre, datos_id in resultados["ids"].items():
        peso_key = id_to_peso_key.get(id_nombre)
        if peso_key in pesos:
            nota_final += datos_id["promedio"] * (pesos[peso_key] / 100)
    
    resultados["final"] = nota_final
    
    return resultados

# ============================================
# 5. INTERFAZ PRINCIPAL - PANEL DE ESTUDIANTES
# ============================================

def mostrar_panel_estudiante():
    """Mostrar interfaz para que los estudiantes califiquen"""
    
    st.title("📝 Sistema de Evaluación por Pares")
    
    # Verificar si la sesión está activa
    if not st.session_state.sesion_activa:
        st.warning("⏸️ La sesión de calificación no está activa. Espera a que el profesor inicie la sesión.")
        return
    
    # Verificar tiempo restante
    if st.session_state.tiempo_fin:
        tiempo_actual = datetime.now()
        if tiempo_actual > st.session_state.tiempo_fin:
            st.error("⏰ El tiempo de calificación ha finalizado.")
            st.session_state.sesion_activa = False
            return
        
        tiempo_restante = st.session_state.tiempo_fin - tiempo_actual
        minutos = int(tiempo_restante.total_seconds() // 60)
        segundos = int(tiempo_restante.total_seconds() % 60)
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.info(f"⏰ Tiempo restante: {minutos:02d}:{segundos:02d}")
    
    # Selección de grupo e ID
    col1, col2 = st.columns(2)
    
    with col1:
        grupos_disponibles = [f"GRUPO {i}" for i in range(1, 9)]
        grupo_seleccionado = st.selectbox(
            "Selecciona tu grupo:",
            grupos_disponibles,
            key="grupo_estudiante"
        )
    
    with col2:
        id_estudiante = st.text_input(
            "Tu ID personal:",
            placeholder="Ej: 202310001",
            key="id_estudiante"
        )
    
    # Verificar si ya calificó
    if grupo_seleccionado and id_estudiante:
        ya_califico = any(
            cal["grupo"] == grupo_seleccionado and cal["id_estudiante"] == id_estudiante
            for cal in st.session_state.datos["calificaciones"]
        )
        
        if ya_califico:
            st.warning("⚠️ Ya has enviado calificaciones para este grupo.")
            return
    
    st.markdown("---")
    
    # Formulario de calificación
    if grupo_seleccionado and id_estudiante:
        st.subheader("Califica cada criterio:")
        
        calificaciones = {}
        
        # Para cada ID de desempeño
        for id_nombre, criterios in RUBRICA_ESTRUCTURA.items():
            with st.expander(f"**{id_nombre}**", expanded=True):
                st.caption(f"Peso en evaluación: {st.session_state.config['pesos'].get(id_nombre[:4], 0)}%")
                
                # Para cada criterio en este ID
                for criterio, codigos in criterios.items():
                    st.markdown(f"#### {criterio}")
                    
                    # Mostrar descriptores si están disponibles
                    if criterio in DESCRIPTORES_EJEMPLO:
                        with st.expander("📋 Ver descriptores de evaluación", expanded=False):
                            for letra, descriptor in DESCRIPTORES_EJEMPLO[criterio].items():
                                st.caption(f"**{letra}**: {descriptor}")
                    
                    # Selector de calificación
                    calificacion = st.selectbox(
                        f"Selecciona calificación para {criterio}:",
                        ["A", "B", "C", "D", "E"],
                        key=f"{id_estudiante}_{grupo_seleccionado}_{criterio}",
                        index=2  # Default a "C" (Bueno)
                    )
                    
                    calificaciones[criterio] = calificacion
        
        # Botón para enviar calificaciones
        if st.button("✅ Enviar Calificaciones", type="primary"):
            if calificaciones:
                # Guardar calificación
                nueva_calificacion = {
                    "id_estudiante": id_estudiante,
                    "grupo": grupo_seleccionado,
                    "calificaciones": calificaciones,
                    "fecha": datetime.now().isoformat()
                }
                
                st.session_state.datos["calificaciones"].append(nueva_calificacion)
                guardar_datos(st.session_state.datos)
                
                st.success("✅ Tus calificaciones han sido registradas exitosamente!")
                st.balloons()
                
                # Limpiar formulario
                time.sleep(2)
                st.rerun()
            else:
                st.error("Debes calificar al menos un criterio.")

# ============================================
# 6. PANEL DEL PROFESOR
# ============================================

def mostrar_panel_profesor():
    """Mostrar panel de control del profesor"""
    
    st.sidebar.title("👨‍🏫 Panel del Profesor")
    
    # Verificación de contraseña
    clave = st.sidebar.text_input(
        "Clave de acceso:",
        type="password",
        key="clave_profesor"
    )
    
    if clave != "MS26":
        st.sidebar.warning("Ingresa la clave para acceder")
        return
    
    st.sidebar.success("✅ Acceso autorizado")
    
    # Gestión de sesiones
    st.sidebar.subheader("🕒 Gestión de Sesiones")
    
    col1, col2 = st.sidebar.columns(2)
    
    with col1:
        if st.button("▶️ Iniciar Sesión", use_container_width=True):
            duracion = st.sidebar.number_input(
                "Duración (minutos):",
                min_value=1,
                max_value=240,
                value=60,
                key="duracion_sesion"
            )
            
            st.session_state.sesion_activa = True
            st.session_state.tiempo_fin = datetime.now() + timedelta(minutes=duracion)
            
            # Registrar sesión
            nueva_sesion = {
                "inicio": datetime.now().isoformat(),
                "fin": st.session_state.tiempo_fin.isoformat(),
                "duracion_minutos": duracion
            }
            
            st.session_state.datos["sesiones"].append(nueva_sesion)
            guardar_datos(st.session_state.datos)
            
            st.sidebar.success(f"Sesión iniciada por {duracion} minutos")
    
    with col2:
        if st.button("⏹️ Finalizar Sesión", use_container_width=True):
            st.session_state.sesion_activa = False
            st.session_state.tiempo_fin = None
            st.sidebar.warning("Sesión finalizada")
    
    # Estado actual
    st.sidebar.subheader("📊 Estado Actual")
    
    if st.session_state.sesion_activa:
        st.sidebar.success("✅ Sesión ACTIVA")
        if st.session_state.tiempo_fin:
            tiempo_restante = st.session_state.tiempo_fin - datetime.now()
            minutos = int(tiempo_restante.total_seconds() // 60)
            segundos = int(tiempo_restante.total_seconds() % 60)
            st.sidebar.info(f"⏳ Tiempo restante: {minutos:02d}:{segundos:02d}")
    else:
        st.sidebar.info("⏸️ Sesión INACTIVA")
    
    total_calificaciones = len(st.session_state.datos["calificaciones"])
    st.sidebar.metric("Calificaciones recibidas", total_calificaciones)
    
    # Configuración de pesos
    st.sidebar.subheader("⚖️ Configurar Pesos")
    
    nuevo_peso_id11 = st.sidebar.slider(
        "Peso ID11 (IDENTIFICAR):",
        min_value=0,
        max_value=100,
        value=st.session_state.config["pesos"]["ID11"],
        key="peso_id11"
    )
    
    nuevo_peso_id12 = st.sidebar.slider(
        "Peso ID12 (FORMULAR):",
        min_value=0,
        max_value=100,
        value=st.session_state.config["pesos"]["ID12"],
        key="peso_id12"
    )
    
    nuevo_peso_id13 = 100 - nuevo_peso_id11 - nuevo_peso_id12
    st.sidebar.metric("Peso ID13 (RESOLVER)", f"{nuevo_peso_id13}%")
    
    if st.sidebar.button("💾 Guardar Pesos", use_container_width=True):
        st.session_state.config["pesos"]["ID11"] = nuevo_peso_id11
        st.session_state.config["pesos"]["ID12"] = nuevo_peso_id12
        st.session_state.config["pesos"]["ID13"] = nuevo_peso_id13
        guardar_configuracion(st.session_state.config)
        st.sidebar.success("Pesos actualizados!")
    
    # Botón para calcular promedios
    st.sidebar.subheader("📈 Calcular Resultados")
    
    if st.sidebar.button("🧮 Calcular Promedios Finales", type="primary", use_container_width=True):
        # Calcular para todos los grupos
        todos_resultados = []
        
        for grupo_num in range(1, 9):
            grupo_id = f"GRUPO {grupo_num}"
            resultados = calcular_promedios_grupo(grupo_id)
            
            if resultados:
                todos_resultados.append(resultados)
        
        # Mostrar resultados en el área principal
        st.session_state.resultados_calculados = todos_resultados
    
    # Resetear datos (con confirmación)
    st.sidebar.subheader("⚠️ Administración")
    
    if st.sidebar.button("🗑️ Limpiar Todas las Calificaciones", use_container_width=True):
        confirmar = st.sidebar.checkbox("Confirmar eliminación")
        if confirmar:
            st.session_state.datos["calificaciones"] = []
            guardar_datos(st.session_state.datos)
            st.sidebar.error("Todas las calificaciones han sido eliminadas")
            st.rerun()

# ============================================
# 7. VISUALIZACIÓN DE RESULTADOS
# ============================================

def mostrar_resultados():
    """Mostrar resultados calculados"""
    
    if 'resultados_calculados' not in st.session_state:
        return
    
    resultados = st.session_state.resultados_calculados
    
    if not resultados:
        st.info("No hay datos suficientes para calcular resultados.")
        return
    
    st.title("📊 Resultados Finales de Evaluación")
    
    # Mostrar resultados por grupo
    for resultado in resultados:
        grupo = resultado["grupo"]
        
        with st.expander(f"**{grupo}** - Nota Final: **{resultado['final']:.2f}/5.0**", expanded=True):
            
            # Tabla de criterios
            st.subheader("Calificaciones por Criterio")
            
            datos_tabla = []
            for criterio, datos in resultado["criterios"].items():
                datos_tabla.append({
                    "Criterio": criterio,
                    "Calificación": datos["cualitativa"],
                    "Nota Numérica": f"{datos['numerica']:.2f}",
                    "Calificaciones Recibidas": datos["total_calificaciones"]
                })
            
            df_criterios = pd.DataFrame(datos_tabla)
            st.dataframe(df_criterios, use_container_width=True)
            
            # Promedios por ID
            st.subheader("Promedios por Indicador de Desempeño")
            
            col1, col2, col3 = st.columns(3)
            
            pesos = st.session_state.config["pesos"]
            
            for i, (id_nombre, datos_id) in enumerate(resultado["ids"].items()):
                with [col1, col2, col3][i % 3]:
                    # Extraer clave del ID para pesos
                    id_key = id_nombre[:4]  # "ID11", "ID12", "ID13"
                    peso = pesos.get(id_key, 0)
                    
                    st.metric(
                        label=id_nombre,
                        value=f"{datos_id['promedio']:.2f}",
                        delta=f"Peso: {peso}%"
                    )
            
            # Nota final detallada
            st.subheader("Cálculo de Nota Final")
            
            calculo_final = []
            for id_nombre, datos_id in resultado["ids"].items():
                id_key = id_nombre[:4]
                peso = pesos.get(id_key, 0) / 100
                contribucion = datos_id["promedio"] * peso
                
                calculo_final.append({
                    "Indicador": id_nombre,
                    "Promedio": f"{datos_id['promedio']:.2f}",
                    "Peso": f"{peso*100:.0f}%",
                    "Contribución": f"{contribucion:.2f}"
                })
            
            df_calculo = pd.DataFrame(calculo_final)
            st.dataframe(df_calculo, use_container_width=True)
            
            st.info(f"**Nota Final Ponderada: {resultado['final']:.2f} / 5.0**")

# ============================================
# 8. APLICACIÓN PRINCIPAL
# ============================================

def main():
    """Función principal de la aplicación"""
    
    # Mostrar panel del profesor en sidebar
    mostrar_panel_profesor()
    
    # Área principal
    if 'resultados_calculados' in st.session_state and st.session_state.resultados_calculados:
        mostrar_resultados()
    else:
        mostrar_panel_estudiante()
    
    # Footer informativo
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.caption("Sistema de Evaluación por Rúbrica - Ingeniería Mecánica")
        st.caption("© 2024 - Universidad Nacional de Colombia")

# ============================================
# 9. EJECUCIÓN
# ============================================

if __name__ == "__main__":
    main()