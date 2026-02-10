import streamlit as st
import pandas as pd
import json
from datetime import datetime, timedelta
from collections import Counter
import os
from typing import Optional

# ============================================
# CONFIGURACIÓN INICIAL
# ============================================

st.set_page_config(
    page_title="Sistema de Evaluación por Rúbrica",
    page_icon="📊",
    layout="wide"
)

# ============================================
# 1. ARCHIVOS Y BLOQUEO (MULTIUSUARIO)
# ============================================

CALIFICACIONES_FILE = "calificaciones.json"
CONFIG_FILE = "configuracion_rubrica.json"
ESTADO_SESION_FILE = "estado_sesion.json"


def _lock_path(path: str) -> str:
    return f"{path}.lock"


def _acquire_lock(lockfile_path: str):
    """
    Lock exclusivo a nivel de archivo (Linux). Streamlit Cloud corre en Linux.
    """
    import fcntl
    f = open(lockfile_path, "a", encoding="utf-8")
    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
    return f  # mantener abierto mientras dure el lock


def _release_lock(lock_handle):
    import fcntl
    try:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
    finally:
        lock_handle.close()


def _load_json_shared(path: str, default: dict):
    """
    Lee JSON usando lock para evitar leer mientras otro escribe.
    Si el archivo no existe, retorna default (no lo crea).
    """
    lock = _acquire_lock(_lock_path(path))
    try:
        if not os.path.exists(path):
            return default
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            # Si quedó corrupto por algún motivo, mejor recuperar con default.
            return default
    finally:
        _release_lock(lock)


def _save_json_shared(path: str, data: dict):
    """
    Escritura atómica + lock.
    Escribe a .tmp y luego hace replace.
    """
    lock = _acquire_lock(_lock_path(path))
    try:
        tmp = f"{path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    finally:
        _release_lock(lock)


# ============================================
# 2. PERSISTENCIA DE DATOS (COMPARTIDA)
# ============================================

def cargar_datos():
    """Cargar calificaciones compartidas (multiusuario)."""
    default = {"calificaciones": [], "sesiones": []}
    datos = _load_json_shared(CALIFICACIONES_FILE, default)
    datos.setdefault("calificaciones", [])
    datos.setdefault("sesiones", [])
    return datos


def guardar_datos(datos):
    """Guardar calificaciones compartidas (multiusuario)."""
    _save_json_shared(CALIFICACIONES_FILE, datos)


def cargar_configuracion():
    """Cargar configuración de rúbrica."""
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)

        if "descriptores" not in config or "pesos" not in config:
            st.error(f"❌ '{CONFIG_FILE}' debe contener 'descriptores' y 'pesos'.")
            st.stop()

        for k in ["ID11", "ID12", "ID13"]:
            config["pesos"].setdefault(k, 0)

        return config

    except FileNotFoundError:
        st.error(f"❌ Archivo '{CONFIG_FILE}' no encontrado en la raíz del repo.")
        st.stop()
    except json.JSONDecodeError:
        st.error(f"❌ El archivo '{CONFIG_FILE}' está corrupto o vacío.")
        st.stop()


def guardar_configuracion(config):
    """Guardar configuración de rúbrica."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.error(f"❌ No se pudo guardar '{CONFIG_FILE}': {e}")


def cargar_estado_sesion():
    """
    Estado GLOBAL compartido para multiusuario.
    Auto-expira si ya pasó el tiempo_fin.
    """
    default = {
        "sesion_activa": False,
        "tiempo_fin": None,
        "duracion_minutos": None,
        "updated_at": None,
        "updated_by": None
    }
    estado = _load_json_shared(ESTADO_SESION_FILE, default)
    for k, v in default.items():
        estado.setdefault(k, v)

    # Auto-expiración
    if estado.get("sesion_activa") and estado.get("tiempo_fin"):
        try:
            fin = datetime.fromisoformat(estado["tiempo_fin"])
            if datetime.now() > fin:
                estado["sesion_activa"] = False
                estado["updated_at"] = datetime.now().isoformat()
                estado["updated_by"] = "auto-expire"
                _save_json_shared(ESTADO_SESION_FILE, estado)
        except Exception:
            estado["sesion_activa"] = False
            estado["tiempo_fin"] = None
            estado["updated_at"] = datetime.now().isoformat()
            estado["updated_by"] = "auto-expire-bad-time"
            _save_json_shared(ESTADO_SESION_FILE, estado)

    return estado


def guardar_estado_sesion(
    sesion_activa: bool,
    tiempo_fin: Optional[datetime],
    duracion_minutos: Optional[int],
    updated_by: str
):
    estado = {
        "sesion_activa": bool(sesion_activa),
        "tiempo_fin": tiempo_fin.isoformat() if tiempo_fin else None,
        "duracion_minutos": int(duracion_minutos) if duracion_minutos is not None else None,
        "updated_at": datetime.now().isoformat(),
        "updated_by": updated_by
    }
    _save_json_shared(ESTADO_SESION_FILE, estado)
    return estado


def sync_estado_global_a_session_state():
    """
    Sincroniza el estado global a la sesión del usuario.
    """
    estado = cargar_estado_sesion()
    st.session_state.sesion_activa = bool(estado.get("sesion_activa", False))
    st.session_state.tiempo_fin = datetime.fromisoformat(estado["tiempo_fin"]) if estado.get("tiempo_fin") else None
    return estado


# ============================================
# 3. INICIALIZACIÓN SESSION STATE
# ============================================

if "datos" not in st.session_state:
    st.session_state.datos = cargar_datos()

if "config" not in st.session_state:
    st.session_state.config = cargar_configuracion()

# Estas dos ahora se sincronizan desde estado_sesion.json
if "sesion_activa" not in st.session_state:
    st.session_state.sesion_activa = False

if "tiempo_fin" not in st.session_state:
    st.session_state.tiempo_fin = None

if "resultados_calculados" not in st.session_state:
    st.session_state.resultados_calculados = None

if "mostrar_datos_brutos" not in st.session_state:
    st.session_state.mostrar_datos_brutos = False


# ============================================
# 4. CONFIGURACIÓN GENERAL
# ============================================

DURACION_PREDETERMINADA = 60
TIEMPO_MINIMO = 15
TIEMPO_MAXIMO = 300

GRUPOS_DISPONIBLES = [f"GRUPO {i}" for i in range(1, 9)]

RUBRICA_ESTRUCTURA = {
    "ID11: IDENTIFICAR": ["C111", "C112"],
    "ID12: FORMULAR": ["C121", "C122"],
    "ID13: RESOLVER": ["C131", "C132", "C133"]
}

SUBCRITERIOS_POR_NIVEL = {"A": "1", "B": "2", "C": "3", "D": "4", "E": "5"}
SUBCRITERIOS_ESPECIALES = {
    "C112": {"A": "6", "B": "7", "C": "8", "D": "9", "E": "10"},
    "C122": {"A": "6", "B": "7", "C": "8", "D": "9", "E": "10"},
    "C132": {"A": "6", "B": "7", "C": "8", "D": "9", "E": "10"},
    "C133": {"A": "11", "B": "12", "C": "13", "D": "14", "E": "15"}
}

RANGOS_NUMERICOS = {
    "A": (4.5, 5.0),
    "B": (4.0, 4.5),
    "C": (3.5, 4.0),
    "D": (3.0, 3.5),
    "E": (0.0, 3.0)
}


# ============================================
# 5. FUNCIONES AUXILIARES
# ============================================

def obtener_codigo_subcriterio(criterio, nivel):
    if criterio in SUBCRITERIOS_ESPECIALES:
        num = SUBCRITERIOS_ESPECIALES[criterio][nivel]
    else:
        num = SUBCRITERIOS_POR_NIVEL[nivel]
    return f"{criterio}{num}"


def obtener_descriptor(criterio, nivel):
    descriptores = st.session_state.config.get("descriptores", {})
    if criterio in descriptores:
        return descriptores[criterio].get(nivel, "Descriptor no disponible")
    return "Descriptor no disponible"


def calcular_moda(calificaciones):
    if not calificaciones:
        return None
    conteo = Counter(calificaciones)
    return conteo.most_common(1)[0][0]


def letra_a_numero(letra):
    if letra not in RANGOS_NUMERICOS:
        return 0.0
    min_val, max_val = RANGOS_NUMERICOS[letra]
    return (min_val + max_val) / 2.0


def obtener_grupos_a_calificar(grupo_afiliacion):
    return [g for g in GRUPOS_DISPONIBLES if g != grupo_afiliacion]


def verificar_calificacion_existente(id_estudiante, grupo_afiliacion, grupo_a_calificar):
    # recargar datos compartidos por si otro usuario escribió
    st.session_state.datos = cargar_datos()

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
    st.session_state.datos = cargar_datos()

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
        "total_evaluadores": len(set(cal["id_estudiante"] for cal in calificaciones_grupo))
    }

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
                    "distribucion": dict(Counter(califs_criterio))
                }

    for id_nombre, criterios in RUBRICA_ESTRUCTURA.items():
        valores_criterios = []
        for criterio in criterios:
            if criterio in resultados["criterios"]:
                valores_criterios.append(resultados["criterios"][criterio]["numerica"])

        if valores_criterios:
            key_peso = id_nombre[:4]
            resultados["ids"][id_nombre] = {
                "promedio": sum(valores_criterios) / len(valores_criterios),
                "peso": st.session_state.config["pesos"].get(key_peso, 0)
            }

    nota_final = 0.0
    for id_nombre, datos_id in resultados["ids"].items():
        key_peso = id_nombre[:4]
        peso = st.session_state.config["pesos"].get(key_peso, 0) / 100.0
        nota_final += datos_id["promedio"] * peso

    resultados["final"] = nota_final
    return resultados


# ============================================
# 6. PANEL ESTUDIANTE
# ============================================

def mostrar_panel_estudiante():
    st.title("📝 Sistema de Evaluación por Pares")

    # Sync desde archivo global (multiusuario)
    sync_estado_global_a_session_state()

    if not st.session_state.sesion_activa:
        st.warning("⏸️ La sesión de calificación no está activa. Espera a que el profesor inicie la sesión.")
        return

    if st.session_state.tiempo_fin:
        tiempo_actual = datetime.now()
        if tiempo_actual > st.session_state.tiempo_fin:
            st.error("⏰ El tiempo de calificación ha finalizado.")
            # Auto-expira global (para que todos lo vean)
            guardar_estado_sesion(False, None, None, updated_by="auto-expire-student")
            st.session_state.sesion_activa = False
            return

        tiempo_restante = st.session_state.tiempo_fin - tiempo_actual
        minutos = int(tiempo_restante.total_seconds() // 60)
        segundos = int(tiempo_restante.total_seconds() % 60)

        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.info(f"⏰ Tiempo restante: {minutos:02d}:{segundos:02d}")

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
            key="grupo_a_calificar"
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
                            st.markdown(f"**{nivel} ({codigo}):** {descriptor}")

                    calificacion = st.selectbox(
                        f"Calificación para {criterio}:",
                        ["A", "B", "C", "D", "E"],
                        key=f"sel_{id_estudiante.strip()}_{grupo_afiliacion}_{grupo_a_calificar}_{criterio}",
                        index=2
                    )

                    calificaciones[criterio] = calificacion

        # --------- ✅ AQUI VA EL CHECKBOX + ENVÍO (DENTRO DE LA FUNCIÓN) ---------
        st.markdown("---")

        confirmado = st.checkbox(
            "Confirmo que revisé todas mis calificaciones antes de enviar.",
            key="confirmacion_envio"
        )

        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            enviar = st.button(
                "✅ Enviar Calificaciones",
                type="primary",
                use_container_width=True,
                disabled=not confirmado
            )

            if enviar:
                if calificaciones:
                    # recargar datos por si cambió entre tanto
                    st.session_state.datos = cargar_datos()

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

                    # 🔄 resetear confirmación para que no quede marcada en la siguiente evaluación
                    st.session_state.confirmacion_envio = False

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
# 7. PANEL PROFESOR
# ============================================

def mostrar_panel_profesor():
    st.sidebar.title("👨‍🏫 Panel del Profesor")

    clave = st.sidebar.text_input("Clave de acceso:", type="password", key="clave_profesor")
    if clave != "MS26":
        st.sidebar.warning("Ingresa la clave para acceder")
        return

    st.sidebar.success("✅ Acceso autorizado")

    # Sync estado global
    sync_estado_global_a_session_state()

    st.sidebar.subheader("🕒 Gestión de Sesiones")

    duracion = st.sidebar.number_input(
        "Duración (minutos):",
        min_value=TIEMPO_MINIMO,
        max_value=TIEMPO_MAXIMO,
        value=int(DURACION_PREDETERMINADA),
        step=5,
        key="duracion_sesion"
    )

    col1, col2 = st.sidebar.columns(2)

    with col1:
        if st.button("▶️ Iniciar Sesión", use_container_width=True):
            fin = datetime.now() + timedelta(minutes=int(duracion))
            guardar_estado_sesion(True, fin, int(duracion), updated_by="profesor")

            # Registrar en calificaciones.json (histórico)
            st.session_state.datos = cargar_datos()
            st.session_state.datos["sesiones"].append({
                "inicio": datetime.now().isoformat(),
                "fin": fin.isoformat(),
                "duracion_minutos": int(duracion)
            })
            guardar_datos(st.session_state.datos)

            st.sidebar.success(f"✅ Sesión iniciada por {int(duracion)} minutos")
            st.rerun()

    with col2:
        if st.button("⏹️ Finalizar Sesión", use_container_width=True):
            guardar_estado_sesion(False, None, None, updated_by="profesor")
            st.sidebar.warning("Sesión finalizada")
            st.rerun()

    # Estado actual (desde archivo global)
    estado = cargar_estado_sesion()
    st.sidebar.subheader("📊 Estado Actual")

    if estado["sesion_activa"]:
        st.sidebar.success("✅ Sesión ACTIVA")
        if estado["tiempo_fin"]:
            fin = datetime.fromisoformat(estado["tiempo_fin"])
            restante = fin - datetime.now()
            if restante.total_seconds() > 0:
                m = int(restante.total_seconds() // 60)
                s = int(restante.total_seconds() % 60)
                st.sidebar.info(f"⏳ Tiempo restante: {m:02d}:{s:02d}")
            else:
                st.sidebar.error("⏰ Tiempo agotado")
    else:
        st.sidebar.info("⏸️ Sesión INACTIVA")

    # Estadísticas (recarga compartida)
    st.session_state.datos = cargar_datos()
    total_calificaciones = len(st.session_state.datos["calificaciones"])
    estudiantes_unicos = len(set(cal["id_estudiante"].upper() for cal in st.session_state.datos["calificaciones"]))

    st.sidebar.metric("Calificaciones recibidas", total_calificaciones)
    st.sidebar.metric("Estudiantes únicos", estudiantes_unicos)

    # Pesos
    st.sidebar.subheader("⚖️ Configurar Pesos")

    pesos = st.session_state.config.get("pesos", {})
    peso_id11_actual = int(pesos.get("ID11", 25))
    peso_id12_actual = int(pesos.get("ID12", 25))

    nuevo_peso_id11 = st.sidebar.slider(
        "Peso ID11 (IDENTIFICAR):",
        min_value=0,
        max_value=100,
        value=peso_id11_actual,
        key="peso_id11"
    )

    max_id12 = max(0, 100 - nuevo_peso_id11)
    valor_id12 = min(peso_id12_actual, max_id12)

    nuevo_peso_id12 = st.sidebar.slider(
        "Peso ID12 (FORMULAR):",
        min_value=0,
        max_value=max_id12,
        value=valor_id12,
        key="peso_id12"
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
            r = calcular_promedios_grupo(grupo)
            if r:
                todos_resultados.append(r)
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
            st.session_state.datos = cargar_datos()
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
# 8. RESULTADOS + DATOS BRUTOS
# ============================================

def mostrar_resultados():
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
        st.metric("Total Evaluadores", sum(r["total_evaluadores"] for r in resultados))
    with col3:
        st.metric("Mejor Nota", f"{max(r['final'] for r in resultados):.2f}")
    with col4:
        st.metric("Peor Nota", f"{min(r['final'] for r in resultados):.2f}")

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
            st.dataframe(pd.DataFrame(datos_tabla), use_container_width=True, hide_index=True)

            st.subheader("📊 Promedios por Indicador")
            cols = st.columns(3)
            for i, (id_nombre, datos_id) in enumerate(resultado["ids"].items()):
                with cols[i % 3]:
                    st.metric(label=id_nombre, value=f"{datos_id['promedio']:.2f}", delta=f"Peso: {datos_id['peso']}%")

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
            st.dataframe(pd.DataFrame(calculo_data), use_container_width=True, hide_index=True)
            st.success(f"### Nota Final del {grupo}: **{resultado['final']:.2f} / 5.0**")


def mostrar_datos_brutos():
    st.title("📁 Datos en Bruto de Calificaciones")

    st.session_state.datos = cargar_datos()
    if not st.session_state.datos["calificaciones"]:
        st.info("No hay datos de calificaciones registrados.")
        return

    datos_brutos = []
    for cal in st.session_state.datos["calificaciones"]:
        fila = {
            "ID Estudiante": cal["id_estudiante"],
            "Grupo Afiliación": cal["grupo_afiliacion"],
            "Grupo Calificado": cal["grupo_calificado"],
            "Fecha": cal["fecha"][:19]
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
        st.bar_chart(df_brutos["Grupo Afiliación"].value_counts().sort_index())
    with col2:
        st.write("**Evaluaciones recibidas por grupo:**")
        st.bar_chart(df_brutos["Grupo Calificado"].value_counts().sort_index())

    if st.button("⬅️ Volver a la vista principal"):
        st.session_state.mostrar_datos_brutos = False
        st.rerun()


# ============================================
# 9. APP PRINCIPAL
# ============================================

def main():
    mostrar_panel_profesor()

    if st.session_state.mostrar_datos_brutos:
        mostrar_datos_brutos()
    elif st.session_state.resultados_calculados:
        mostrar_resultados()
    else:
        mostrar_panel_estudiante()

    st.markdown("---")
    st.caption("Sistema de Evaluación por Rúbrica - Ingeniería Mecánica")
    st.caption("© 2025-2026 - UPB University | Created by HV MartínezTejada")


if __name__ == "__main__":
    main()
