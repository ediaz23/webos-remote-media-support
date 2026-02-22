#!/usr/bin/env bash
set -euo pipefail

SO="${1:-}"
if [[ -z "$SO" || ! -e "$SO" ]]; then
  echo "Uso: $0 /ruta/a/libwrms_libass.so"
  exit 1
fi

echo "== Archivo =="
echo "  $SO"
echo

echo "== RUNPATH/RPATH =="
readelf -d "$SO" 2>/dev/null | awk '
  /\(RPATH\)|\(RUNPATH\)/ {print "  " $0}
' || true
echo

echo "== NEEDED (deps dinámicas; estas SI se buscan afuera en runtime) =="
mapfile -t NEEDED < <(readelf -d "$SO" 2>/dev/null | awk -F'[][]' '/\(NEEDED\)/{print $2}')
if (( ${#NEEDED[@]} == 0 )); then
  echo "  (ninguna)"
else
  for lib in "${NEEDED[@]}"; do
    echo "  - $lib"
  done
fi
echo

echo "== ldd (resolución real en esta máquina) =="
LDD_OUT="$(ldd "$SO" 2>&1 || true)"
echo "$LDD_OUT" | sed 's/^/  /'
echo

echo "== FALTANTES (not found) =="
MISSING="$(echo "$LDD_OUT" | awk '/not found/{print $1}' || true)"
if [[ -z "${MISSING// }" ]]; then
  echo "  OK (no faltan .so)"
else
  echo "$MISSING" | sed 's/^/  - /'
fi
echo

echo "== Dónde se está resolviendo cada NEEDED =="
if (( ${#NEEDED[@]} == 0 )); then
  echo "  (sin NEEDED)"
else
  for lib in "${NEEDED[@]}"; do
    resolved="$(echo "$LDD_OUT" | awk -v L="$lib" '$1==L {print $3}' || true)"
    if [[ -z "$resolved" || "$resolved" == "not" ]]; then
      # algunos ldd imprimen distinto cuando es linux-vdso o ld-linux
      resolved="$(echo "$LDD_OUT" | awk -v L="$lib" '$1==L {print $2" "$3}' || true)"
    fi
    if echo "$LDD_OUT" | awk -v L="$lib" '$1==L && /not found/ {exit 0} {exit 1}' 2>/dev/null; then
      echo "  - $lib -> NOT FOUND"
    else
      # fallback: busca línea por regex si no matchea exacto
      line="$(echo "$LDD_OUT" | grep -E "^\s*$lib(\s|$)" || true)"
      if [[ -n "$line" ]]; then
        echo "  - $line"
      else
        echo "  - $lib -> (no aparece en ldd; puede estar linkeada estática o ser indirecta)"
      fi
    fi
  done
fi
echo

echo "== Símbolos no resueltos (nm -u) =="
# Nota: undefined a libc/libstdc++/etc es normal si esas deps están en NEEDED.
# Esto solo ayuda a ver si quedó algo colgando que NO se resuelve por NEEDED.
if command -v nm >/dev/null 2>&1; then
  nm -u "$SO" 2>/dev/null | head -50 | sed 's/^/  /' || true
  echo "  (mostrando primeros 50)"
else
  echo "  nm no está disponible"
fi
echo

echo "== Resultado =="
if [[ -z "${MISSING// }" ]]; then
  echo "  ✅ Carga en ESTA máquina (no hay 'not found')."
  echo "  ℹ️ Si quieres 'TODO dentro', entonces cualquier cosa listada en NEEDED NO está dentro."
else
  echo "  ❌ Le faltan librerías en runtime: ver sección FALTANTES."
fi