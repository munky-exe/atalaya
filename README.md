# Atalaya

[![CI](https://github.com/munky-exe/atalaya/actions/workflows/ci.yml/badge.svg)](https://github.com/munky-exe/atalaya/actions/workflows/ci.yml)

**Vigila la postura TLS de tus dominios, no solo si responden.**

Un monitor de uptime te dice que el sitio esta arriba. Atalaya te dice que el
certificado vence en nueve dias, que sigue aceptando TLS 1.1 y que la cadena
de confianza no valida, antes de que lo descubran tus usuarios.

    git clone https://github.com/munky-exe/atalaya.git
    cd atalaya
    docker compose up

Abre http://localhost:8080

## Que revisa

Un handshake TLS pasivo por dominio, y de ahi sale todo:

| Senal | Por que importa |
|---|---|
| Dias restantes del certificado | La causa mas comun de caida evitable |
| Ventana completa de vigencia | 38 dias restantes significan algo muy distinto en un certificado de 90 dias que en uno de dos anos |
| Version del protocolo | TLS 1.0 y 1.1 estan declarados obsoletos por el RFC 8996 |
| Protocolos que el servidor acepta | Negociar TLS 1.3 no prueba que el servidor haya dejado de ofrecer TLS 1.0 |
| Fuerza del cifrador | Menos de 128 bits ya no es aceptable |
| Validacion de la cadena | Detecta autofirmados, emisores desconocidos y cadenas incompletas |
| Correspondencia del nombre | El certificado ampara el dominio que realmente visitas |
| Vigencia superior a 398 dias | Las CA publicas dejaron de emitirlos; casi siempre delata un certificado interno |

Cada hallazgo trae severidad y una explicacion de que hacer, no solo un codigo.

## La barra de vida

El elemento central del panel es la ventana completa de validez del
certificado con un marcador para hoy.

La mayoria de las herramientas imprime "vence en 38 dias" y te deja adivinar
si eso es temprano o tarde. Aqui la proporcion de vida restante se ve de un
vistazo, y el color va de frio a calido conforme se acerca el vencimiento.

## Tres estados, no dos

Un monitor de seguridad que dice "limpio" cuando en realidad no miro es peor
que uno que no revisa nada: entrena a la gente a confiar en algo que no lo
merece. Por eso los protocolos obsoletos tienen tres respuestas distintas:

- **Acepta TLS 1.0 / 1.1** — evidencia dura, hallazgo critico
- **Sin comprobar: el sondeo tardo demasiado** — nos rendimos por tiempo
- **Sin comprobar: este OpenSSL no puede negociarlos** — limitacion nuestra

Solo la primera afecta la calificacion.

## Como esta armado

    web    React + TypeScript + Tailwind    ->  nginx
    api    FastAPI + SQLAlchemy async       ->  uvicorn
    db     PostgreSQL 16

La tabla checks es de solo anexado: nada actualiza un chequeo despues de
escribirlo. Eso convierte el historial en un registro auditable y permite
responder "desde cuando esta asi", que es la pregunta real cuando algo se
rompe.

Las decisiones de diseno estan en [ARCHITECTURE.md](ARCHITECTURE.md).

## Desarrollo

Backend con recarga automatica:

    cd api
    python3.12 -m venv .venv && source .venv/bin/activate
    pip install -r requirements-dev.txt
    uvicorn app.main:app --reload --reload-dir app

Frontend:

    cd web
    npm install
    npm run dev

Documentacion interactiva de la API en http://localhost:8000/docs

### Pruebas

    cd api
    pytest -q
    ruff check .

Las 62 pruebas no tocan la red ni necesitan Postgres: el motor de
calificacion es una funcion pura y la API corre contra SQLite en memoria.
La suite completa termina en menos de un segundo.

## Configuracion

Copia .env.example a .env. Todo tiene un valor que sirve en local.

| Variable | Por defecto | Para que |
|---|---|---|
| WEB_PORT | 8080 | Puerto del panel |
| API_PORT | 8000 | Puerto de la API |
| DB_PORT | 5432 | Puerto de Postgres |
| CORS_ORIGINS | localhost:8080,localhost:5173 | Origenes permitidos |

## Hoja de ruta

- [x] **Fase 1** — Chequeo TLS, historial, panel, Compose, CI
- [ ] **Fase 2** — Worker con Redis: chequeos programados, reintentos con espera exponencial
- [ ] **Fase 3** — Cuentas, equipos, alertas por webhook y correo, graficas de evolucion
- [ ] **Fase 4** — Metricas Prometheus, tablero Grafana, despliegue continuo

## Alcance

Atalaya observa; no ataca. Abre una conexion TLS y lee lo que el servidor
presenta publicamente a cualquier navegador. No escanea puertos, no prueba
credenciales y no envia trafico malformado. Vigila dominios que administres
o que sean publicos.

## Licencia

MIT
