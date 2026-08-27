# Atalaya

Vigila la postura TLS de tus dominios, no solo si responden.

Un monitor de uptime te dice que el sitio está arriba. Atalaya te dice que el
certificado vence en nueve días y que sigue negociando TLS 1.1 — antes de que
lo descubran tus usuarios.

Estado: en construcción.

## Limitación conocida

Algunos dominios tardan decenas de segundos en el sondeo, y el tiempo no se
va en el handshake sino en la resolución DNS, que en Python es una llamada
bloqueante del sistema sin parámetro de tiempo. Ningún timeout del módulo
`socket` la corta.

Se atiende en la Fase 2: cuando el sondeo ocurra en un worker en segundo
plano, agregar un dominio responderá al instante y la lentitud del servidor
dejará de ser lentitud del usuario.
