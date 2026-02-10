import streamlit as st
import pandas as pd
import json
from datetime import datetime, timedelta
from collections import Counter

# ============================================
# CONFIGURACIÓN INICIAL
# ============================================

st.set_page_config(
    page_title="Sistema de Evaluación por Rúbrica",
    page_icon="📊",
    layout="wide"
)

# ============================================
# 1. SISTEMA DE PERSISTENCIA DE DATOS
# ============================================

CALIFICACIONES_FILE = "calificaciones.json"
CONFIG_FILE = "configuracion_rubrica.json"


def cargar_datos():
    """Cargar datos desde archivo JSON de calificaciones."""
    try:
        with open(CALIFICACIONES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"calificaciones": [], "sesiones": []}
    except json.JSONDecodeError:
        st.error(f"❌ El archivo '{CALIFICACIONES_FILE}' está corrupto o vacío.")
        st.stop()


def guardar_datos(datos):
    """Guardar datos en archivo JSON de calificaciones."""
    try:
        with open(CALIFICACIONES_FILE, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.error(f"❌ No se pudo guardar '{CALIFICACIONES_FILE}': {e}")


def cargar_configuracion():
    """Cargar configuración de la rúbrica (descriptores y pesos)."""
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)

        # Validación mínima esperada
        if "descriptores" not in config or "pesos" not in config:
            st.error(f"❌ '{CONFIG_FILE}' debe contener las llaves: 'descriptores' y 'pesos'.")
            st.stop()

        # Asegurar claves de pesos esperadas
        for k in ["ID11", "ID12", "ID13"]:
            config["pesos"].setdefault(k, 0)

        return config

    except FileNotFoundError:
        st.error(f"❌ Archivo '{CONFIG_FILE}' no encontrado.")
        st.error("Crea este archivo en la raíz del proyecto con los descriptores y pesos.")
        st.stop()
    except json.JSONDecodeError:
        st.error(f"❌ El archivo '{CONFIG_FILE}' está corrupto o vacío.")
        st.stop()


def guardar_configuracion(config):
    """Guardar configuración de la rúbrica (pesos y descriptores)."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.error(f"❌ No se pudo guardar la configuración en '{CONFIG_FILE}': {e}")


# ============================================
# 2. INICIALIZACIÓN DEL ESTADO DE LA SESIÓN
# ============================================

if "datos" not in st.session_state:
    st.session_state.datos = cargar_datos()

if "config" not in st.session_state:
    st.session_state.config = cargar_configuracion()

if "sesion_activa" not in st.session_state:
    st.session_state.sesion_activa = False

if "tiempo_fin" not in st.session_state:
    st.session_state.tiempo_fin = None

if "resultados_calculados" not in st.session_state:
    st.session_state.resultados_calculados = None

if "mostrar_datos_brutos" not in st.session_state:
    st.session_state.mostrar_datos_brutos = False


# ============================================
# 3. CONFIGURACIÓN - AQUÍ PUEDES MODIFICAR VALORES
# ============================================

DURACION_PREDETERMINADA = 60   # Minutos por defecto (1 hora)
TIEMPO_MINIMO = 15             # Mínimo de minutos permitidos
TIEMPO_MAXIMO = 300            # Máximo de minutos permitidos (5 horas)

GRUPOS_DISPONIBLES = [f"GRUPO {i}" for i in range(1, 9)]

RUBRICA_ESTRUCTURA = {
    "ID11: IDENTIFICAR": ["C111", "C112"],
    "ID12: FORMULAR": ["C121", "C122"],
    "ID13: RESOLVER": ["C131", "C132", "C133"],
}

SUBCRITERIOS_POR_NIVEL = {"A": "1", "B": "2", "C": "3", "D": "4", "E": "5"}
SUBCRITERIOS_ESPECIALES = {
    "C112": {"A": "6", "B": "7", "C": "8", "D": "9", "E": "10"},
    "C122": {"A": "6", "B": "7", "C": "8", "D": "9", "E": "10"},
    "C132": {"A": "6", "B": "7", "C": "8", "D": "9", "E": "10"},
    "C133": {"A": "11", "B": "12", "C": "13", "D": "14", "E": "15"},
}

RANGOS_NUMERICOS = {
    "A": (4.5, 5.0),
    "B": (4.0, 4.5),
    "C": (3.5, 4.0),
    "D": (3.0, 3.5),
    "E": (0.0, 3.0),
}


# ============================================
# 4. FUNCIONES AUXILIARES
# ============================================

def obtener_codigo_subcriterio(criterio, nivel):
    """Obtener el código completo del subcriterio (ej: C1111)."""
    if criterio in SUBCRITERIOS_ESPECIALES:
        num = SUBCRITERIOS_ESPECIALES[criterio][nivel]
    else:
        num = SUBCRITERIOS_POR_NIVEL[nivel]
    return f"{criterio}{num}"


def obtener_descriptor(criterio, nivel):
    """Obtener el descriptor para un criterio y nivel específico."""
    descriptores = st.session_state.config.get("descriptores", {})
    if criterio in descriptores:
        return descriptores[criterio].get(nivel, "Descriptor no disponible")
    return "Descriptor no disponible"


def calcular_moda(calificaciones):
    """Calcular la moda (valor más frecuente) de una lista."""
    if not calificaciones:
        return None
    conteo = Counter(calificaciones)
    return conteo.most_common(1)[0][0]


def letra_a_numero(letra):
    """Convertir letra de calificación a valor numérico central."""
    if letra not in RANGOS_NUMERICOS:
        return 0.0
    min_val, max_val = RANGOS_NUMERICOS[letra]
    return (min_val + max_val) / 2.0


def obtener_grupos_a_calificar(grupo_afiliacion):
    """Obtener lista de grupos que se pueden calificar (excluyendo el propio)."""
    return [g for g in GRUPOS_DISPONIBLES if g != grupo_afiliacion]


def verificar_calificacion_existente(id_estudiante, grupo_afiliacion, grupo_a_calificar):
    """Verificar si el estudiante ya calificó a este grupo."""
    id_limpio = id_estudiante.strip().upper()
    for cal in st.session_state.datos["calificaciones"]:
        if (
            cal["id_estudiante"].upper() == id_limpio
            and cal["grupo_afiliacion"] == grupo_afiliacion
            and cal["grupo_calificado"] == grupo_a_calificar
        ):
            return True
    return False


def calcular_promedios_grupo(grupo_calificado):
    """Calcular promedios para un grupo específico."""
    calificaciones_grupo = [
        cal for cal in st.session_state.datos["calificaciones"]
        if cal["grupo_calificado"] == grupo_calificado
    ]

    if not calificaciones_grupo:
        return None

    resultados = {
        "grupo_calificado": grupo_calificado,
        "criterios": {},
        "ids": {},
        "final": 0.0,
        "total_evaluadores": len(set(cal["id_estudiante"] for cal in calificaciones_grupo)),
    }

    # Moda por criterio
    for id_nombre, criterios in RUBRICA_ESTRUCTURA.items():
        for criterio in criterios:
            califs_criterio = [
                cal["calificaciones"].get(criterio)
                for cal in calificaciones_grupo
                if criterio in cal["calificaciones"]
            ]
            califs_criterio = [c for c in califs_criterio if c is not None]

            if califs_criterio:
                moda = calcular_moda(califs_criterio)
                resultados["criterios"][criterio] = {
                    "cualitativa": moda,
                    "numerica": letra_a_numero(moda),
                    "total_calificaciones": len(califs_criterio),
                    "codigo_subcriterio": obtener_codigo_subcriterio(criterio, moda),
                    "descriptor": obtener_descriptor(criterio, moda),
                    "distribucion": dict(Counter(califs_criterio)),
                }

    # Promedio por ID (ID11/ID12/ID13)
    for id_nombre, criterios in RUBRICA_ESTRUCTURA.items():
        valores_criterios = []
        for criterio in criterios:
            if criterio in resultados["criterios"]:
                valores_criterios.append(resultados["criterios"][criterio]["numerica"])

        if valores_criterios:
            key_peso = id_nombre[:4]  # "ID11", "ID12", ...
            resultados["ids"][id_nombre] = {
                "promedio": sum(valores_criterios) / len(valores_criterios),
                "peso": st.session_state.config["pesos"].get(key_peso, 0),
            }

    # Nota final ponderada
    nota_final = 0.0
    for id_nombre, datos_id in resultados["ids"].items():
        key_peso = id_nombre[:4]
        peso = st.session_state.config["pesos"].get(key_peso, 0) / 100.0
        nota_final += datos_id["promedio"] * peso

    resultados["final"] = nota_final
    return resultados


# ============================================
# 5. INTERFAZ PRINCIPAL - PANEL DE ESTUDIANTES
# ============================================

def mostrar_panel_estudiante():
    """Mostrar interfaz para que los estudiantes califiquen."""
    st.title("📝 Sistema de Evaluación por Pares")

    if not st.session_state.sesion_activa:
        st.warning("⏸️ La sesión de calificación no está activa. Espera a que el profesor inicie la sesión.")
        return

    # Tiempo restante
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

    # Info estudiante
    st.subheader("👤 Información del Estudiante")
    col1, col2 = st.columns(2)

    with col1:
        id_estudiante = st.text_input("Tu ID personal:", placeholder="Ej: 202310001", key="id_estudiante")

    with col2:
        grupo_afiliacion = st.selectbox("Grupo al que perteneces:", GRUPOS_DISPONIBLES, key="grupo_afiliacion")

    st.markdown("---")

    if id_estudiante and grupo_afiliacion:
        if not id_estudiante.strip():
            st.error("Por favor, ingresa tu ID personal.")
            return

        st.subheader("🎯 Selección del Grupo a Evaluar")

        grupos_a_calificar = obtener_grupos_a_calificar(grupo_afiliacion)
        if not grupos_a_calificar:
            st.error("No hay grupos disponibles para calificar.")
            return

        grupo_a_calificar = st.selectbox(
            "Selecciona el grupo a calificar:",
            grupos_a_calificar,
            key="grupo_a_calificar",
        )

        st.info(f"**Tu grupo:** {grupo_afiliacion} | **Grupo a calificar:** {grupo_a_calificar}")

        if verificar_calificacion_existente(id_estudiante, grupo_afiliacion, grupo_a_calificar):
            st.warning(f"⚠️ Ya has calificado al {grupo_a_calificar}.")
            st.info("Puedes seleccionar otro grupo para calificar.")
            return

        st.markdown("---")
        st.subheader("📋 Formulario de Calificación")

        calificaciones = {}

        for id_nombre, criterios in RUBRICA_ESTRUCTURA.items():
            with st.expander(f"**{id_nombre}**", expanded=True):
                peso = st.session_state.config["pesos"].get(id_nombre[:4], 0)
                st.caption(f"Peso en evaluación: {peso}%")

                for criterio in criterios:
                    st.markdown(f"#### {criterio}")

                    with st.expander("📖 Ver descriptores de evaluación (A a E)", expanded=False):
                        for nivel in ["A", "B", "C", "D", "E"]:
                            codigo = obtener_codigo_subcriterio(criterio, nivel)
                            descriptor = obtener_descriptor(criterio, nivel)
                            # Mostrar completo (no truncado) o truncado si quieres:
                            st.markdown(f"**{nivel} ({codigo}):** {descriptor}")

                    calificacion = st.selectbox(
                        f"Calificación para {criterio}:",
                        ["A", "B", "C", "D", "E"],
                        key=f"sel_{id_estudiante.strip()}_{grupo_afiliacion}_{grupo_a_calificar}_{criterio}",
                        index=2,
                    )

                    calificaciones[criterio] = calificacion

        st.markdown("---")
        col1, col2, col3 = st.columns([1, 2, 1])

        with col2:
            if st.button("✅ Enviar Calificaciones", type="primary", use_container_width=True):
                if calificaciones:
                    nueva_calificacion = {
                        "id_estudiante": id_estudiante.strip(),
                        "grupo_afiliacion": grupo_afiliacion,
                        "grupo_calificado": grupo_a_calificar,
                        "calificaciones": calificaciones,
                        "fecha": datetime.now().isoformat(),
                    }

                    st.session_state.datos["calificaciones"].append(nueva_calificacion)
                    guardar_datos(st.session_state.datos)

                    st.success("✅ ¡Tus calificaciones han sido registradas exitosamente!")
                    st.balloons()

                    with st.expander("📋 Ver resumen de tu evaluación", expanded=True):
                        st.write(f"**Evaluador:** {id_estudiante.strip()} (del {grupo_afiliacion})")
                        st.write(f"**Grupo evaluado:** {grupo_a_calificar}")
                        st.write("**Calificaciones asignadas:**")

                        for criterio, letra in calificaciones.items():
                            codigo = obtener_codigo_subcriterio(criterio, letra)
                            st.write(f"- {criterio}: **{letra}** ({codigo})")

                    st.markdown("---")
                    if st.button("📝 Calificar Otro Grupo"):
                        st.rerun()
                else:
                    st.error("Debes calificar al menos un criterio.")


# ============================================
# 6. PANEL DEL PROFESOR
# ============================================

def mostrar_panel_profesor():
    """Mostrar panel de control del profesor."""
    st.sidebar.title("👨‍🏫 Panel del Profesor")

    clave = st.sidebar.text_input("Clave de acceso:", type="password", key="clave_profesor")

    if clave != "MS26":
        st.sidebar.warning("Ingresa la clave para acceder")
        return

    st.sidebar.success("✅ Acceso autorizado")

    # Gestión de sesiones (RECOMENDACIÓN APLICADA: duration input fuera del botón)
    st.sidebar.subheader("🕒 Gestión de Sesiones")

    duracion = st.sidebar.number_input(
        "Duración (minutos):",
        min_value=TIEMPO_MINIMO,
        max_value=TIEMPO_MAXIMO,
        value=int(DURACION_PREDETERMINADA),
        step=5,
        key="duracion_sesion",
    )

    col1, col2 = st.sidebar.columns(2)

    with col1:
        if st.button("▶️ Iniciar Sesión", use_container_width=True):
            st.session_state.sesion_activa = True
            st.session_state.tiempo_fin = datetime.now() + timedelta(minutes=int(duracion))

            nueva_sesion = {
                "inicio": datetime.now().isoformat(),
                "fin": st.session_state.tiempo_fin.isoformat(),
                "duracion_minutos": int(duracion),
            }

            st.session_state.datos["sesiones"].append(nueva_sesion)
            guardar_datos(st.session_state.datos)

            st.sidebar.success(f"✅ Sesión iniciada por {int(duracion)} minutos")
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
            if tiempo_restante.total_seconds() > 0:
                minutos = int(tiempo_restante.total_seconds() // 60)
                segundos = int(tiempo_restante.total_seconds() % 60)
                st.sidebar.info(f"⏳ Tiempo restante: {minutos:02d}:{segundos:02d}")
            else:
                st.sidebar.error("⏰ Tiempo agotado")
    else:
        st.sidebar.info("⏸️ Sesión INACTIVA")

    # Estadísticas
    total_calificaciones = len(st.session_state.datos["calificaciones"])
    estudiantes_unicos = len(set(cal["id_estudiante"].upper() for cal in st.session_state.datos["calificaciones"]))

    st.sidebar.metric("Calificaciones recibidas", total_calificaciones)
    st.sidebar.metric("Estudiantes únicos", estudiantes_unicos)

    # Configuración de pesos (RECOMENDACIÓN APLICADA: evitar sumas >100)
    st.sidebar.subheader("⚖️ Configurar Pesos")

    pesos = st.session_state.config.get("pesos", {})
    peso_id11_actual = int(pesos.get("ID11", 25))
    peso_id12_actual = int(pesos.get("ID12", 25))

    nuevo_peso_id11 = st.sidebar.slider(
        "Peso ID11 (IDENTIFICAR):",
        min_value=0,
        max_value=100,
        value=peso_id11_actual,
        key="peso_id11",
    )

    max_id12 = max(0, 100 - nuevo_peso_id11)
    # Ajustar valor por si el actual quedó fuera del nuevo rango
    valor_id12 = min(peso_id12_actual, max_id12)

    nuevo_peso_id12 = st.sidebar.slider(
        "Peso ID12 (FORMULAR):",
        min_value=0,
        max_value=max_id12,
        value=valor_id12,
        key="peso_id12",
    )

    nuevo_peso_id13 = 100 - nuevo_peso_id11 - nuevo_peso_id12
    st.sidebar.metric("Peso ID13 (RESOLVER)", f"{nuevo_peso_id13}%")

    if st.sidebar.button("💾 Guardar Pesos", use_container_width=True):
        st.session_state.config["pesos"]["ID11"] = int(nuevo_peso_id11)
        st.session_state.config["pesos"]["ID12"] = int(nuevo_peso_id12)
        st.session_state.config["pesos"]["ID13"] = int(nuevo_peso_id13)

        guardar_configuracion(st.session_state.config)
        st.sidebar.success("✅ Pesos actualizados!")
        st.rerun()

    # Calcular resultados
    st.sidebar.subheader("📈 Calcular Resultados")

    if st.sidebar.button("🧮 Calcular Promedios Finales", type="primary", use_container_width=True):
        todos_resultados = []
        for grupo in GRUPOS_DISPONIBLES:
            resultados = calcular_promedios_grupo(grupo)
            if resultados:
                todos_resultados.append(resultados)

        st.session_state.resultados_calculados = todos_resultados
        st.sidebar.success(f"✅ Resultados calculados para {len(todos_resultados)} grupos")
        st.rerun()

    # Administración
    st.sidebar.subheader("⚠️ Administración")

    if st.sidebar.button("🗑️ Limpiar Todas las Calificaciones", use_container_width=True):
        st.sidebar.warning("Esta acción eliminará TODAS las calificaciones.")
        confirmar = st.sidebar.checkbox("Confirmar eliminación")
        texto_confirmacion = st.sidebar.text_input("Escribe 'CONFIRMAR' para proceder:")

        if confirmar and texto_confirmacion == "CONFIRMAR":
            st.session_state.datos["calificaciones"] = []
            guardar_datos(st.session_state.datos)
            st.session_state.resultados_calculados = None
            st.sidebar.error("Todas las calificaciones han sido eliminadas")
            st.rerun()

    # Datos en bruto
    st.sidebar.subheader("📁 Datos en Bruto")
    if st.sidebar.button("📋 Ver Datos Completos", use_container_width=True):
        st.session_state.mostrar_datos_brutos = True
        st.rerun()


# ============================================
# 7. VISUALIZACIÓN DE RESULTADOS
# ============================================

def mostrar_resultados():
    """Mostrar resultados calculados."""
    resultados = st.session_state.resultados_calculados

    if not resultados:
        st.info("No hay datos suficientes para calcular resultados.")
        return

    st.title("📊 Resultados Finales de Evaluación")

    st.subheader("📈 Resumen General")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Grupos Evaluados", len(resultados))

    with col2:
        total_evaluadores = sum(r["total_evaluadores"] for r in resultados)
        st.metric("Total Evaluadores", total_evaluadores)

    with col3:
        mejor_nota = max(r["final"] for r in resultados) if resultados else 0
        st.metric("Mejor Nota", f"{mejor_nota:.2f}")

    with col4:
        peor_nota = min(r["final"] for r in resultados) if resultados else 0
        st.metric("Peor Nota", f"{peor_nota:.2f}")

    st.markdown("---")

    for resultado in resultados:
        grupo = resultado["grupo_calificado"]

        with st.expander(
            f"**{grupo}** - Nota Final: **{resultado['final']:.2f}/5.0** "
            f"(Evaluadores: {resultado['total_evaluadores']})",
            expanded=False
        ):
            st.subheader("📋 Calificaciones por Criterio")

            datos_tabla = []
            for criterio, datos in resultado["criterios"].items():
                distribucion = ", ".join([f"{k}: {v}" for k, v in datos["distribucion"].items()])
                datos_tabla.append({
                    "Criterio": criterio,
                    "Calificación": datos["cualitativa"],
                    "Subcriterio": datos["codigo_subcriterio"],
                    "Nota": f"{datos['numerica']:.2f}",
                    "Votos": datos["total_calificaciones"],
                    "Distribución": distribucion
                })

            df_criterios = pd.DataFrame(datos_tabla)
            st.dataframe(df_criterios, use_container_width=True, hide_index=True)

            st.subheader("📊 Promedios por Indicador")
            cols = st.columns(3)
            for i, (id_nombre, datos_id) in enumerate(resultado["ids"].items()):
                with cols[i % 3]:
                    st.metric(
                        label=id_nombre,
                        value=f"{datos_id['promedio']:.2f}",
                        delta=f"Peso: {datos_id['peso']}%"
                    )

            st.subheader("🧮 Cálculo de Nota Final")
            calculo_data = []
            for id_nombre, datos_id in resultado["ids"].items():
                peso = datos_id["peso"] / 100.0
                contribucion = datos_id["promedio"] * peso

                calculo_data.append({
                    "Indicador": id_nombre,
                    "Promedio": f"{datos_id['promedio']:.2f}",
                    "Peso": f"{datos_id['peso']}%",
                    "Contribución": f"{contribucion:.2f}"
                })

            calculo_data.append({
                "Indicador": "**TOTAL FINAL**",
                "Promedio": "",
                "Peso": "100%",
                "Contribución": f"**{resultado['final']:.2f}**"
            })

            df_calculo = pd.DataFrame(calculo_data)
            st.dataframe(df_calculo, use_container_width=True, hide_index=True)

            st.success(f"### Nota Final del {grupo}: **{resultado['final']:.2f} / 5.0**")


def mostrar_datos_brutos():
    """Mostrar datos en bruto para el profesor."""
    st.title("📁 Datos en Bruto de Calificaciones")

    if not st.session_state.datos["calificaciones"]:
        st.info("No hay datos de calificaciones registrados.")
        return

    datos_brutos = []
    for cal in st.session_state.datos["calificaciones"]:
        fila = {
            "ID Estudiante": cal["id_estudiante"],
            "Grupo Afiliación": cal["grupo_afiliacion"],
            "Grupo Calificado": cal["grupo_calificado"],
            "Fecha": cal["fecha"][:19],
        }
        for criterio, valor in cal["calificaciones"].items():
            fila[criterio] = valor
        datos_brutos.append(fila)

    df_brutos = pd.DataFrame(datos_brutos)
    st.dataframe(df_brutos, use_container_width=True, height=400)

    st.subheader("📊 Estadísticas")
    col1, col2 = st.columns(2)

    with col1:
        st.write("**Evaluadores por grupo de afiliación:**")
        distrib_afiliacion = df_brutos["Grupo Afiliación"].value_counts().sort_index()
        st.bar_chart(distrib_afiliacion)

    with col2:
        st.write("**Evaluaciones recibidas por grupo:**")
        distrib_calificado = df_brutos["Grupo Calificado"].value_counts().sort_index()
        st.bar_chart(distrib_calificado)

    if st.button("⬅️ Volver a la vista principal"):
        st.session_state.mostrar_datos_brutos = False
        st.rerun()


# ============================================
# 8. APLICACIÓN PRINCIPAL
# ============================================

def main():
    """Función principal de la aplicación."""
    mostrar_panel_profesor()

    if st.session_state.mostrar_datos_brutos:
        mostrar_datos_brutos()
    elif st.session_state.resultados_calculados:
        mostrar_resultados()
    else:
        mostrar_panel_estudiante()

    st.markdown("---")
    st.caption("Sistema de Evaluación por Rúbrica - Ingeniería Mecánica")
    st.caption("© 2025 2026 - UPB University | Created by HV MartínezTejada")


# ============================================
# 9. EJECUCIÓN
# ============================================

if __name__ == "__main__":
    main()

