# CI de Inventarios — diagnóstico y estrategia

> **Relevado:** 2026-09-20 sobre la API de GitHub · **Workflows:** ninguno
> **Estrategia común de los proyectos:** repositorio de infraestructura, privado
> **Estado:** actualizado el 2026-10-27 — `doc/gateway/` saneado y ramas alineadas; el CI sigue sin existir
>
> ⚠️ **Este repositorio es público.** Aquí no van direcciones de servidores, rutas de despliegue,
> nombres de ficheros de clave ni referencias a otros proyectos.

## El dato: no hay CI de ningún tipo

```
origin/main       ficheros de workflow: 0
origin/staging    ficheros de workflow: 0
origin/develop    ficheros de workflow: 0
```

Cero workflows en las tres ramas. Cero ejecuciones en el historial de Actions. **Cero correos de
fallo**, y esa cifra es engañosa: no hay ruido porque no hay nada escuchando.

Este proyecto está **en producción y tiene datos de cliente**. Es de los que más razones tiene para
tener una comprobación automática y de los que menos tiene.

## Qué significa no tener CI aquí

No es que falten pruebas. Es que **no hay ningún punto en el que algo pueda detenerse antes de
llegar a producción**:

- Nada comprueba que el código compile o que las pruebas pasen antes de mezclar a `main`.
- Nada impide que `staging` y `develop` deriven de `main` en silencio. El repositorio tiene además
  una rama `merge/unify-staging-develop`, que sugiere que esa deriva ya ocurrió al menos una vez.
- Nada detecta una dependencia con vulnerabilidad conocida: **Dependabot está deshabilitado**.

En otro proyecto del servidor, una corrección de CI se quedó en una rama y la de producción pasó
once días en rojo sin que nadie lo notara. Allí al menos **había** un CI que se puso rojo. Aquí no
habría nada que ponerse rojo.

## La oportunidad que no se está usando

Por ser público, este repositorio tiene **gratis** cosas que los privados del mismo plan no pueden
tener:

| Capacidad | Estado hoy |
|---|---|
| Minutos de GitHub Actions ilimitados | sin usar — 0 workflows |
| *Rulesets* y protección de rama | disponibles, **0 configurados** |
| Escaneo de secretos | ✅ activo |
| Protección de push de secretos | ✅ activo |

Los repositorios privados de la misma cuenta reciben `403 Upgrade to GitHub Pro` al pedir protección
de rama. Aquí está disponible y no se usa. **Es la protección más barata del inventario: cuesta
cero.**

## 🔴 Documentación de infraestructura publicada en este repositorio

Encontrado el 2026-09-20. Es el hallazgo más importante de este documento y no tiene que ver con el
CI.

La carpeta `doc/gateway/` de este repositorio **público** contiene cinco documentos de operación del
servidor, cuatro de ellos copiados del repositorio de infraestructura, que es privado:

```
doc/gateway/vps-estado-actual.md
doc/gateway/conectar-proyecto-gateway.md
doc/gateway/desarrollo-local.md
doc/gateway/migracion-runbook.md
doc/gateway/ambientes-produccion-staging.md
```

**No contienen ninguna credencial real**, y eso está bien hecho: los valores sensibles aparecen como
instrucciones de generación y el propio texto indica que los secretos viven fuera de git, con
permisos 600.

Lo que sí queda público es el mapa del servidor: nombre de host y dirección, sistema operativo,
versión de kernel y de Docker, ocupación de disco, el diagrama del gateway, la tabla DNS completa de
los subdominios, las rutas de despliegue y **la ruta exacta del fichero donde viven los secretos**.

Ninguno de esos datos abre nada por sí solo. Juntos ahorran a un atacante toda la fase de
reconocimiento.

> **Cómo llegó aquí:** no fue una fuga, fue una copia. La documentación del gateway se trajo al
> repositorio del proyecto para tenerla a mano, y este repositorio es público. El patrón es siempre
> el mismo: **algo se pone donde es cómodo, no donde corresponde, y el daño aparece meses después.**

### Decisión (2026-10-27): sanear

Se eligió la opción 2:

- `vps-estado-actual.md` y `migracion-runbook.md` se sustituyeron por un aviso que apunta a
  `micronuba-infra`. Eran datos del servidor y de otros proyectos, sin nada propio de Inventarios.
- `ambientes-produccion-staging.md` se saneó: la IP, el ID de zona de Cloudflare, los
  directorios de despliegue, la ruta de un volcado de la base de datos, el comando para leer el
  `.env` y el email del super_admin pasaron a marcadores. De paso se puso al día.
- `desarrollo-local.md` y `conectar-proyecto-gateway.md` se mantienen: solo hablan de la
  máquina local (`localhost`, dominios `.local`).

El historial de git conserva las versiones anteriores, a propósito (ver abajo).

Las tres opciones que se consideraron, y no son equivalentes:

1. **Borrar los cinco documentos** y dejar un puntero al repositorio de infraestructura. Coherente,
   pero quien trabaje aquí pierde la documentación de su gateway.
2. **Sanear**: sustituir host, dirección y rutas por marcadores, conservando lo demás.
3. **Hacer privado este repositorio**, a costa de las cuatro capacidades gratuitas de la tabla
   anterior.

En los tres casos **sin reescribir el historial**: un `push --force` sobre un repositorio público
rompe clones y forks, y el dato más expuesto —la dirección del servidor— se resuelve igualmente
desde el DNS de los subdominios.

## Una pregunta abierta que hay que responder

Este repositorio es **público** y contiene una plataforma con datos de cliente en producción.

No se asume que sea un error: puede ser deliberado. Pero es una decisión con consecuencias —el código
es legible por cualquiera, incluidas las rutas de la aplicación y su modelo de datos— y **no está
escrita en ninguna parte**. O se documenta la razón, o se cambia la visibilidad.

Si se hiciera privado, se perderían las cuatro capacidades gratuitas de la tabla anterior. Conviene
decidirlo sabiendo eso. El hallazgo anterior es un argumento de peso para revisarlo.

## Qué se va a hacer

Decidido el 2026-09-20.

| # | Acción | Estado |
|---|---|---|
| 1 | **Decidir qué hacer con `doc/gateway/`** — borrar, sanear o hacer privado el repositorio | ✅ saneado el 2026-10-27 |
| 2 | **Decidir y documentar la visibilidad** del repositorio | pendiente |
| 3 | Configurar un *ruleset* en `main`: sin push directo (gratuito aquí) | pendiente |
| 4 | Añadir un CI mínimo: instalar dependencias, linter y las pruebas que existan | pendiente |
| 5 | Una vez haya CI, exigirlo como *status check* en el *ruleset* | pendiente |
| 6 | Habilitar Dependabot | 🟢 **no espera a nada** |
| 7 | Resolver la deriva entre `main`, `staging` y `develop` | ✅ las tres en el mismo commit desde el 2026-10-27 (falta impedir que vuelva: pasos 3 y 5) |

El orden importa. **Los pasos 1 y 2 son la misma decisión mirada desde dos lados** y conviene
tomarlos juntos. El paso 3 protege desde hoy sin escribir una línea de CI; el 4 es más trabajo y
puede esperar.

Sobre el paso 3: un CI mínimo que solo instale dependencias y corra el linter ya detecta la mayoría
de lo que rompe un despliegue. No hace falta una suite completa para que valga la pena. **Es mejor un
CI pobre que se ejecuta que uno completo que nunca se escribe.**

## Las reglas que quedan

1. **Un proyecto con datos de cliente en producción tiene CI.** Aunque sea mínimo.
2. **Cero correos de fallo no significa que todo vaya bien.** Puede significar que nadie está
   mirando. Aquí significa lo segundo.
3. **Lo que es gratuito y protege, se activa.** Los *rulesets* de este repositorio no cuestan nada y
   están sin configurar.
4. **Este repositorio es público y se trata como público.** Nada de direcciones de servidores, rutas
   de despliegue, nombres de claves ni datos de otros proyectos, en el código ni en la documentación.
