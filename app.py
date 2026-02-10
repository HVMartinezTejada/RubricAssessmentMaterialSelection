import streamlit as st
import pandas as pd
import json
from datetime import datetime, timedelta
from collections import Counter
import time

# Configuración inicial de la página
st.set_page_config(
    page_title="Sistema de Evaluación por Rúbrica",
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
        st.error("❌ Archivo 'configuracion_rubrica.json' no encontrado. Crea este archivo con los descriptores.")
        st.stop()

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

# ============================================
# 3. DEFINICIÓN DE ESTRUCTURAS DE DATOS
# ============================================

# Lista de todos los grupos disponibles
GRUPOS_DISPONIBLES = [f"GRUPO {i}" for i in range(1, 9)]

# Estructura de criterios por ID
RUBRICA_ESTRUCTURA = {
    "ID11: IDENTIFICAR": ["C111", "C112"],
    "ID12: FORMULAR": ["C121", "C122"],
    "ID13: RESOLVER": ["C131", "C132", "C133"]
}

# Mapeo de niveles A-E a sus códigos de subcriterio
SUBCRITERIOS_POR_NIVEL = {
    "A": "1",
    "B": "2",
    "C": "3",
    "D": "4",
    "E": "5"
}

# Para C112, C122, C132, C133 los códigos son diferentes
SUBCRITERIOS_ESPECIALES = {
    "C112": {"A": "6", "B": "7", "C": "8", "D": "9", "E": "10"},
    "C122": {"A": "6", "B": "7", "C": "8", "D": "9", "E": "10"},
    "C132": {"A": "6", "B": "7", "C": "8", "D": "9", "E": "10"},
    "C133": {"A": "11", "B": "12", "C": "13", "D": "14", "E": "15"}
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
# 4. FUNCIONES AUXILIARES
# ============================================

def obtener_codigo_subcriterio(criterio, nivel):
    """Obtener el código completo del subcriterio (ej: C1111)"""
    if criterio in SUBCRITERIOS_ESPECIALES:
        num = SUBCRITERIOS_ESPECIALES[criterio][nivel]
    else:
        num = SUBCRITERIOS_POR_NIVEL[nivel]
    return f"{criterio}{num}"

def obtener_descriptor(criterio, nivel):
    """Obtener el descriptor para un criterio y nivel específico"""
    if criterio in st.session_state.config["descriptores"]:
        return st.session_state.config["descriptores"][criterio].get(nivel, "Descriptor no disponible")
    return "Descriptor no disponible"

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

def obtener_grupos_a_calificar(grupo_afiliacion):
    """Obtener lista de grupos que se pueden calificar (excluyendo el propio)"""
    return [g for g in GRUPOS_DISPONIBLES if g != grupo_afiliacion]

def verificar_calificacion_existente(id_estudiante, grupo_afiliacion, grupo_a_calificar):
    """Verificar si el estudiante ya calificó a este grupo"""
    for cal in st.session_state.datos["calificaciones"]:
        if (cal["id_estudiante"] == id_estudiante and 
            cal["grupo_afiliacion"] == grupo_afiliacion and
            cal["grupo_calificado"] == grupo_a_calificar):
            return True
    return False

def calcular_promedios_grupo(grupo_calificado):
    """Calcular promedios para un grupo específico (basado en las calificaciones recibidas)"""
    # Filtrar calificaciones para el grupo calificado
    calificaciones_grupo = [
        cal for cal in st.session_state.datos["calificaciones"]
        if cal["grupo_calificado"] == grupo_calificado
    ]
    
    if not calificaciones_grupo:
        return None
    
    # Estructura para resultados
    resultados = {
        "grupo_calificado": grupo_calificado,
        "criterios": {},
        "ids": {},
        "final": 0.0,
        "total_evaluadores": len(set(cal["id_estudiante"] for cal in calificaciones_grupo))
    }
    
    # Calcular moda por criterio
    for id_nombre, criterios in RUBRICA_ESTRUCTURA.items():
        for criterio in criterios:
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
                    "total_calificaciones": len(califs_criterio),
                    "codigo_subcriterio": obtener_codigo_subcriterio(criterio, moda),
                    "descriptor": obtener_descriptor(criterio, moda),
                    "distribucion": dict(Counter(califs_criterio))
                }
    
    # Calcular promedio por ID
    for id_nombre, criterios in RUBRICA_ESTRUCTURA.items():
        valores_criterios = []
        for criterio in criterios:
            if criterio in resultados["criterios"]:
                valores_criterios.append(resultados["criterios"][criterio]["numerica"])
        
        if valores_criterios:
            resultados["ids"][id_nombre] = {
                "promedio": sum(valores_criterios) / len(valores_criterios),
                "peso": st.session_state.config["pesos"].get(id_nombre[:4], 0)
            }
    
    # Calcular nota final ponderada
    nota_final = 0.0
    
    for id_nombre, datos_id in resultados["ids"].items():
        peso_key = id_nombre[:4]
        peso = st.session_state.config["pesos"].get(peso_key, 0) / 100
        nota_final += datos_id["promedio"] * peso
    
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
    
    # Paso 1: Información del estudiante
    st.subheader("👤 Información del Estudiante")
    
    col1, col2 = st.columns(2)
    
    with col1:
        id_estudiante = st.text_input(
            "Tu ID personal:",
            placeholder="Ej: 202310001",
            key="id_estudiante"
        )
    
    with col2:
        grupo_afiliacion = st.selectbox(
            "Grupo al que perteneces:",
            GRUPOS_DISPONIBLES,
            key="grupo_afiliacion"
        )
    
    st.markdown("---")
    
    # Paso 2: Selección del grupo a calificar
    if id_estudiante and grupo_afiliacion:
        if not id_estudiante.strip():
            st.error("Por favor, ingresa tu ID personal.")
            return
        
        st.subheader("🎯 Selección del Grupo a Evaluar")
        
        # Obtener grupos que se pueden calificar (excluyendo el propio)
        grupos_a_calificar = obtener_grupos_a_calificar(grupo_afiliacion)
        
        if not grupos_a_calificar:
            st.error("No hay grupos disponibles para calificar.")
            return
        
        grupo_a_calificar = st.selectbox(
            "Selecciona el grupo a calificar:",
            grupos_a_calificar,
            key="grupo_a_calificar"
        )
        
        st.info(f"**Tu grupo:** {grupo_afiliacion} | **Grupo a calificar:** {grupo_a_calificar}")
        
        # Verificar si ya calificó a este grupo
        if verificar_calificacion_existente(id_estudiante.strip(), grupo_afiliacion, grupo_a_calificar):
            st.warning(f"⚠️ Ya has calificado al {grupo_a_calificar}. No puedes enviar otra calificación para el mismo grupo.")
            return
        
        st.markdown("---")
        
        # Paso 3: Formulario de calificación
        st.subheader("📋 Formulario de Calificación")
        st.info(f"Estás evaluando al **{grupo_a_calificar}** (Tú perteneces al {grupo_afiliacion})")
        
        calificaciones = {}
        
        # Para cada ID de desempeño
        for id_nombre, criterios in RUBRICA_ESTRUCTURA.items():
            with st.expander(f"**{id_nombre}**", expanded=True):
                peso = st.session_state.config["pesos"].get(id_nombre[:4], 0)
                st.caption(f"Peso en evaluación: {peso}%")
                
                # Para cada criterio en este ID
                for criterio in criterios:
                    st.markdown(f"#### {criterio}")
                    
                    # Mostrar todos los descriptores (subcriterios)
                    with st.expander("📖 Ver descriptores de evaluación (A a E)", expanded=False):
                        for nivel in ["A", "B", "C", "D", "E"]:
                            codigo = obtener_codigo_subcriterio(criterio, nivel)
                            descriptor = obtener_descriptor(criterio, nivel)
                            st.markdown(f"**{nivel} ({codigo}):** {descriptor}")
                    
                    # Selector de calificación
                    calificacion = st.selectbox(
                        f"Calificación para {criterio}:",
                        ["A", "B", "C", "D", "E"],
                        key=f"{id_estudiante}_{grupo_afiliacion}_{grupo_a_calificar}_{criterio}",
                        index=2
                    )
                    
                    calificaciones[criterio] = calificacion
        
        # Botón para enviar calificaciones
        st.markdown("---")
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col2:
            if st.button("✅ Enviar Calificaciones", type="primary", use_container_width=True):
                if calificaciones:
                    # Guardar calificación
                    nueva_calificacion = {
                        "id_estudiante": id_estudiante.strip(),
                        "grupo_afiliacion": grupo_afiliacion,
                        "grupo_calificado": grupo_a_calificar,
                        "calificaciones": calificaciones,
                        "fecha": datetime.now().isoformat()
                    }
                    
                    st.session_state.datos["calificaciones"].append(nueva_calificacion)
                    guardar_datos(st.session_state.datos)
                    
                    st.success("✅ ¡Tus calificaciones han sido registradas exitosamente!")
                    st.balloons()
                    
                    # Mostrar resumen
                    st.info("**Resumen de tu evaluación:**")
                    st.write(f"**Evaluador:** {id_estudiante.strip()} (del {grupo_afiliacion})")
                    st.write(f"**Grupo evaluado:** {grupo_a_calificar}")
                    st.write("**Calificaciones asignadas:**")
                    
                    for criterio, letra in calificaciones.items():
                        codigo = obtener_codigo_subcriterio(criterio, letra)
                        st.write(f"- {criterio}: **{letra}** ({codigo})")
                    
                    # Opción para calificar otro grupo
                    st.markdown("---")
                    if st.button("📝 Calificar Otro Grupo"):
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
                max_value=300,
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
            st.rerun()
    
    with col2:
        if st.button("⏹️ Finalizar Sesión", use_container_width=True):
            st.session_state.sesion_activa = False
            st.session_state.tiempo_fin = None
            st.sidebar.warning("Sesión finalizada")
            st.rerun()
    
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
    
    # Estadísticas
    total_calificaciones = len(st.session_state.datos["calificaciones"])
    estudiantes_unicos = len(set(
        cal["id_estudiante"] for cal in st.session_state.datos["calificaciones"]
    ))
    
    st.sidebar.metric("Calificaciones recibidas", total_calificaciones)
    st.sidebar.metric("Estudiantes participantes", estudiantes_unicos)
    
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
        st.rerun()
    
    # Botón para calcular promedios
    st.sidebar.subheader("📈 Calcular Resultados")
    
    if st.sidebar.button("🧮 Calcular Promedios Finales", type="primary", use_container_width=True):
        # Calcular para todos los grupos
        todos_resultados = []
        
        for grupo in GRUPOS_DISPONIBLES:
            resultados = calcular_promedios_grupo(grupo)
            if resultados:
                todos_resultados.append(resultados)
        
        # Guardar resultados en session state
        st.session_state.resultados_calculados = todos_resultados
        st.sidebar.success(f"Resultados calculados para {len(todos_resultados)} grupos")
        st.rerun()
    
    # Resetear datos (con confirmación)
    st.sidebar.subheader("⚠️ Administración")
    
    if st.sidebar.button("🗑️ Limpiar Todas las Calificaciones", use_container_width=True):
        st.sidebar.warning("Esta acción eliminará TODAS las calificaciones.")
        confirmar = st.sidebar.checkbox("Confirmar eliminación (escribe 'CONFIRMAR' abajo)")
        texto_confirmacion = st.sidebar.text_input("Escribe 'CONFIRMAR' para proceder:")
        
        if confirmar and texto_confirmacion == "CONFIRMAR":
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
        grupo = resultado["grupo_calificado"]
        
        with st.expander(f"**{grupo}** - Nota Final: **{resultado['final']:.2f}/5.0** (Evaluadores: {resultado['total_evaluadores']})", expanded=True):
            
            # Tabla de criterios con subcriterios
            st.subheader("Calificaciones por Criterio (Moda del Grupo)")
            
            datos_tabla = []
            for criterio, datos in resultado["criterios"].items():
                datos_tabla.append({
                    "Criterio": criterio,
                    "Calif. Cualitativa": datos["cualitativa"],
                    "Subcriterio": datos["codigo_subcriterio"],
                    "Nota Numérica": f"{datos['numerica']:.2f}",
                    "Calificaciones": datos["total_calificaciones"]
                })
            
            df_criterios = pd.DataFrame(datos_tabla)
            st.dataframe(df_criterios, use_container_width=True, hide_index=True)
            
            # Promedios por ID
            st.subheader("📈 Promedios por Indicador de Desempeño")
            
            col1, col2, col3 = st.columns(3)
            
            for i, (id_nombre, datos_id) in enumerate(resultado["ids"].items()):
                col = [col1, col2, col3][i % 3]
                with col:
                    st.metric(
                        label=id_nombre,
                        value=f"{datos_id['promedio']:.2f}",
                        delta=f"Peso: {datos_id['peso']}%"
                    )
            
            # Nota final detallada
            st.subheader("🧮 Cálculo de Nota Final Ponderada")
            
            calculo_final = []
            for id_nombre, datos_id in resultado["ids"].items():
                peso = datos_id["peso"] / 100
                contribucion = datos_id["promedio"] * peso
                
                calculo_final.append({
                    "Indicador": id_nombre,
                    "Promedio": f"{datos_id['promedio']:.2f}",
                    "Peso": f"{datos_id['peso']}%",
                    "Contribución": f"{contribucion:.2f}"
                })
            
            # Agregar total
            calculo_final.append({
                "Indicador": "**TOTAL FINAL**",
                "Promedio": "",
                "Peso": "100%",
                "Contribución": f"**{resultado['final']:.2f}**"
            })
            
            df_calculo = pd.DataFrame(calculo_final)
            st.dataframe(df_calculo, use_container_width=True, hide_index=True)
            
            st.success(f"### Nota Final del {grupo}: **{resultado['final']:.2f} / 5.0**")

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
        st.caption("© 2025 - UPB University | Created by HV MartínezTejada")

# ============================================
# 9. EJECUCIÓN
# ============================================

if __name__ == "__main__":
    main()


