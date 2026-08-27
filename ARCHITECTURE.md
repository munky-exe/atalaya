# Decisiones de arquitectura

Este documento explica **por que** el proyecto esta armado asi, no que hace
cada archivo. Son las decisiones que se toman una vez y se pagan durante todo
el proyecto.

## Flujo de una peticion

    navegador -> nginx (web) -> React
                                  |
                                  v  fetch /api/domains
                              FastAPI (api)
                                  |
                       +----------+----------+
                       v                     v
                probe() en hilo         SQLAlchemy async
                (socket bloqueante)          |
                       |                     v
                       +----> grade() -> PostgreSQL
                             (pura)

## La calificacion es una funcion pura

`probe()` habla con la red. `grade()` no. Recibe una `Observation` y devuelve
un veredicto, siempre el mismo para la misma entrada.

Esta separacion es la decision mas importante del proyecto:

- La logica de negocio se prueba sin red, sin certificados de prueba y sin
  esperar timeouts. La suite completa corre en menos de un segundo.
- Las reglas de calificacion se discuten y ajustan leyendo un solo archivo.
- Cuando llegue el worker de la Fase 2, importara `grade()` sin arrastrar
  FastAPI.

La alternativa —mezclar el socket y las reglas en un solo metodo— es lo que
convierte una suite de pruebas en algo que nadie corre.

## El sondeo bloqueante corre en un hilo

`ssl` y `socket` son sincronos. Llamarlos directo desde un handler `async`
congelaria el event loop durante todo el handshake, y con timeout de 8
segundos eso significa que un dominio lento bloquea a todos los demas.

`asyncio.to_thread` lo mueve al threadpool. Es la solucion correcta aqui
porque el trabajo es de E/S, no de CPU.

## Doble intento en el handshake

Un certificado vencido hace fallar la verificacion, y una conexion fallida no
devuelve certificado. Si nos quedaramos ahi, el peor caso —el que mas nos
importa— produciria el reporte mas vacio.

Por eso `probe()` reintenta sin verificacion cuando la validacion falla,
unicamente para leer el certificado. La razon del fallo se guarda aparte y se
convierte en un hallazgo. **Nunca se confia en ese certificado, solo se lee.**

Medido en expired.badssl.com: sin el segundo intento, cero datos. Con el,
emisor COMODO, sujeto *.badssl.com y fecha de vencimiento exacta.

## La verificacion delega al almacen del sistema

Python en macOS no usa el llavero del sistema sino el paquete de raices de
OpenSSL. Con la configuracion por defecto, gob.mx y unam.mx aparecian con la
cadena rota siendo perfectamente validos.

truststore delega la verificacion al almacen nativo, que es lo que hace un
navegador. Un monitor de seguridad con falsos positivos entrena a la gente a
ignorar sus alertas.

## checks es de solo anexado

Nada actualiza un chequeo despues de escribirlo. Cada sondeo agrega una fila.

Se paga en espacio y se cobra en todo lo demas: historial auditable, graficas
de evolucion sin tablas extra, y la posibilidad de responder "desde cuando
esta asi", que es la pregunta que de verdad se hace en una guardia.

El indice compuesto (domain_id, observed_at) sostiene esas consultas.

## El engine se construye perezosamente

create_async_engine a nivel de modulo se ejecuta al importar. Eso hace que
importar app.main exija el driver de Postgres instalado y una URL valida,
incluso en una prueba que va a usar SQLite.

Con lru_cache sobre get_engine(), el engine se crea la primera vez que alguien
lo pide. Las pruebas sobreescriben la dependencia get_session y nunca lo
piden. Tres lineas que eliminan una dependencia completa del entorno de
pruebas.

## selectinload en lugar de carga perezosa

Listar veinte dominios con su ultimo chequeo son dos consultas, no veintiuna.
El N+1 no se nota con diez registros de prueba y tumba el panel con
doscientos.

En SQLAlchemy async hay una razon extra: la carga perezosa simplemente no
existe. Tocar una relacion sin haberla pedido revienta con MissingGreenlet,
porque no se puede hacer E/S implicita fuera del await. Es incomodo al
principio, pero obliga a ser consciente de cada consulta.

## Los hallazgos van en JSON, no en su propia tabla

Se leen siempre completos junto con su chequeo y nunca se consultan por
separado. Normalizarlos agregaria un JOIN a cada lectura para resolver un
problema que no existe.

Si algun dia hiciera falta responder "cuantos dominios tienen TLS obsoleto",
esa consulta justificaria una tabla. Hoy no.

## Compose espera a que Postgres este sano

depends_on a secas solo espera a que el contenedor exista, lo que ocurre
varios segundos antes de que Postgres acepte conexiones. De ahi sale el
clasico "funciona al segundo docker compose up".

El healthcheck con pg_isready mas condition: service_healthy lo resuelve de
verdad.

## Imagenes multietapa

La etapa de construccion tiene compilador y cabeceras de desarrollo; la de
ejecucion no. La imagen final no lleva nada con lo que compilar codigo, y
corre como usuario sin privilegios con UID 10001.

## La URL de la API es argumento de construccion

Vite incrusta las variables VITE_* en el bundle al compilar. No hay forma de
cambiarlas en tiempo de ejecucion sin volver a servir los archivos.

Es una limitacion real de las SPA estaticas: cambiar el destino de la API
significa reconstruir la imagen. Se documenta en lugar de fingir que existe
configuracion en caliente.

## Lo que deliberadamente no esta

- **Autenticacion** — llega en la Fase 3. Meterla ahora complicaria cada
  prueba antes de que exista algo que proteger.
- **Alembic** — la Fase 1 usa create_all. Las migraciones tienen sentido
  cuando el esquema empieza a cambiar bajo datos que importan.
- **WebSockets** — los chequeos tardan segundos, no milisegundos. Un boton
  que refresca es honesto; un canal en vivo seria adorno.
- **Chequeos en segundo plano** — es la Fase 2, y la razon esta medida: con
  el sondeo dentro de la peticion HTTP, el usuario paga la lentitud del
  servidor mas lento. unam.mx tardaba 32 segundos y ninguna optimizacion de
  timeouts arregla eso de raiz.
