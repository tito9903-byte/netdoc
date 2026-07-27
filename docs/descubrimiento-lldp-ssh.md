# Descubrimiento de conexiones LLDP por SSH

## Objetivo

NetDoc puede consultar un dispositivo por SSH, ejecutar el comando LLDP apropiado para su plataforma y comparar los vecinos anunciados con los dispositivos e interfaces registrados en NetBox.

El módulo no crea cables automáticamente durante la consulta. El flujo es:

1. conectarse por SSH usando una cuenta de solo lectura;
2. entrar a modo privilegiado cuando el perfil tenga `use_enable=true`;
3. ejecutar LLDP;
4. normalizar la salida;
5. identificar el dispositivo y la interfaz remota en NetBox;
6. verificar que ambos extremos estén libres;
7. presentar una propuesta individual;
8. crear únicamente ese cable después de la confirmación del usuario.

Un solo cable de NetBox documenta los dos extremos. NetDoc no crea una conexión duplicada en el dispositivo remoto.

## Plataformas preparadas

- Arista EOS;
- Cisco IOS e IOS XE;
- Cisco NX-OS;
- Juniper Junos;
- MikroTik RouterOS.

Netmiko administra la sesión CLI y solicita a NTC Templates una salida estructurada cuando existe una plantilla compatible. Si la plataforma devuelve texto, NetDoc utiliza parsers de respaldo específicos para Arista, Cisco IOS/IOS XE, Cisco NX-OS, Junos y RouterOS.

Arista EOS utiliza una preparación de sesión propia que detecta el prompt y desactiva el paginador sin ejecutar el cambio de ancho de terminal incompatible con algunas versiones antiguas de EOS.

## Configuración del entorno

El descubrimiento permanece deshabilitado por defecto.

```env
NETDOC_SSH_DISCOVERY_ENABLED=true
NETDOC_SSH_CONNECT_TIMEOUT=10
NETDOC_SSH_COMMAND_TIMEOUT=30
NETDOC_SSH_MAX_NEIGHBORS=256
```

Los perfiles se guardan como JSON dentro del `.env`:

```env
NETDOC_SSH_PROFILES_JSON='{"default":{"username":"netdoc-read","password":"CAMBIAR","port":22,"use_enable":false},"arista_eos":{"use_enable":true,"secret":"CAMBIAR_ENABLE"},"cisco_ios":{},"cisco_nxos":{},"juniper_junos":{},"mikrotik_routeros":{}}'
```

El perfil `default` se hereda. Cada plataforma puede reemplazar cualquier valor:

```env
NETDOC_SSH_PROFILES_JSON='{"default":{"username":"netdoc-read","password":"CLAVE_GENERAL","port":22,"use_enable":false},"arista_eos":{"username":"netdoc-arista","password":"CLAVE_ARISTA","use_enable":true,"secret":"CLAVE_ENABLE_ARISTA"},"juniper_junos":{"private_key_file":"/etc/netdoc/ssh/juniper_read"}}'
```

Campos admitidos dentro de cada perfil:

- `username`;
- `password`;
- `private_key_file` o `key_file`;
- `use_enable` o `enter_enable`;
- `secret`, contraseña utilizada al ejecutar `enable`;
- `port`;
- `device_type`, para sobrescribir el controlador de Netmiko;
- `command`, para usar una variante específica del comando LLDP.

### Modo enable

NetDoc no ejecuta `enable` en todas las plataformas. Solo lo hace cuando el perfil efectivo contiene:

```json
{"use_enable": true, "secret": "CLAVE_ENABLE"}
```

La secuencia es:

```text
SSH
→ comprobar modo privilegiado
→ ejecutar enable si todavía no está privilegiado
→ comprobar nuevamente el prompt
→ ejecutar el comando LLDP
```

Si `use_enable=true` y falta `secret`, NetDoc detiene la operación antes de conectarse y muestra un error de configuración. Si el usuario ya entra directamente en modo privilegiado, Netmiko lo detecta y no envía `enable` innecesariamente.

En Junos y RouterOS normalmente debe mantenerse `use_enable=false`, porque esas plataformas no utilizan el flujo clásico de `enable` de Cisco/EOS.

Las credenciales nunca se guardan en NetBox ni en la auditoría.

## Permisos de archivos

El `.env` debe permanecer fuera de Git y tener permisos restrictivos:

```bash
chown sshtelenord:sshtelenord /opt/netdoc-dev/.env
chmod 600 /opt/netdoc-dev/.env
```

Para llaves privadas:

```bash
install -d -m 700 -o sshtelenord -g sshtelenord /etc/netdoc/ssh
chown sshtelenord:sshtelenord /etc/netdoc/ssh/netdoc_read
chmod 600 /etc/netdoc/ssh/netdoc_read
```

La cuenta configurada en los equipos debe tener acceso únicamente a comandos de consulta. No debe poder entrar a configuración, reiniciar equipos ni cambiar servicios.

## Datos requeridos en NetBox

Cada dispositivo debe tener:

1. una IP principal IPv4 o IPv6 accesible desde el servidor de NetDoc para establecer SSH;
2. una plataforma reconocible, por ejemplo `arista_eos`, `cisco_ios`, `cisco_nxos`, `juniper_junos` o `mikrotik_routeros`;
3. interfaces cuyos nombres puedan compararse con los anunciados por LLDP.

Opcionalmente puede utilizarse el campo personalizado:

```text
netdoc_ssh_profile
```

El valor selecciona un perfil del JSON del entorno y también puede ayudar a identificar la plataforma. Ejemplo:

```text
netdoc_ssh_profile = arista_eos
```

## Uso

1. Abrir la ficha del dispositivo.
2. Ir a la sección **Interfaces**.
3. Pulsar **Descubrir LLDP**.
4. Revisar la IP, plataforma, perfil SSH y comando que utilizará NetDoc.
5. Pulsar **Ejecutar LLDP por SSH**.
6. Revisar cada propuesta y el campo **Identificado por**.
7. Seleccionar el tipo físico del cable solo en la propuesta deseada.
8. Pulsar **Confirmar y documentar**.

Cada tarjeta es independiente. Confirmar una propuesta no crea ni modifica las demás.

## Identificación del dispositivo remoto

NetDoc no utiliza la IP como referencia principal obligatoria. El orden de selección es:

1. coincidencia exacta del nombre LLDP;
2. coincidencia del nombre corto sin dominio DNS;
3. coincidencia única de la IP anunciada con cualquier dirección IP asignada al dispositivo en NetBox.

La IP puede ser principal o secundaria. Si el nombre coincide pero la IP LLDP no está asignada al mismo dispositivo, la propuesta no se bloquea: la pantalla indica que el equipo fue identificado por nombre y conserva la IP como evidencia.

Cuando el nombre no coincide pero la IP anunciada identifica un único dispositivo y ambos puertos existen y están libres, la propuesta puede confirmarse. La pantalla lo marca explícitamente como **IP principal** o **IP asignada** para que el usuario sepa cómo se reconoció el vecino.

Una IP nunca reemplaza una coincidencia única de nombre. Esto evita que una dirección de administración anunciada por LLDP dirija la propuesta hacia otro equipo cuando el nombre identifica correctamente al vecino.

## Estados de una propuesta

### Lista para confirmar

- existe la interfaz local en NetBox;
- el vecino coincide con un dispositivo por nombre o por una IP única;
- existe la interfaz remota;
- ambos extremos están libres.

### Interfaz ocupada en NetBox

Alguno de los extremos ya tiene un cable o un extremo conectado. NetDoc no sobrescribe la conexión.

### Requiere revisión

No se pudo identificar de forma segura el dispositivo remoto o su interfaz. No se permite forzar una conexión sin coincidencia de ambos extremos.

## Confianza

La puntuación combina:

- coincidencia exacta del nombre;
- coincidencia del nombre sin dominio DNS;
- coincidencia de la IP anunciada con una IP principal o secundaria asignada;
- coincidencia de la interfaz local;
- coincidencia de la interfaz remota.

La confianza ayuda a revisar las propuestas, pero no sustituye la confirmación humana. El campo **Identificado por** es la referencia explícita del método utilizado.

## Normalización de interfaces

NetDoc normaliza abreviaturas frecuentes antes de comparar, por ejemplo:

- `Gi1/0/1` y `GigabitEthernet1/0/1`;
- `Te1/0/1` y `TenGigabitEthernet1/0/1`;
- `Eth49` y `Ethernet49`;
- `Port-Channel1` y `Po1`.

Los nombres propios de Junos y RouterOS se conservan con cambios mínimos.

## Seguridad y trazabilidad

- La consulta requiere el permiso `connections.view`.
- La creación del cable requiere `devices.create` y escritura habilitada.
- Cada propuesta se firma y vence después de 15 minutos.
- Antes de crear el cable se vuelven a consultar ambos extremos en NetBox.
- Los resultados y errores se registran en la auditoría de NetDoc.
- Las contraseñas, el `secret`, las llaves y la salida completa del equipo no se guardan en la auditoría.

## Limitaciones actuales

- El descubrimiento se ejecuta por un dispositivo a la vez.
- La solicitud web espera a que termine el comando SSH.
- No existe todavía validación bidireccional automática desde el vecino.
- No se crean dispositivos o interfaces faltantes desde LLDP.
- No se eliminan cables cuando un vecino deja de anunciarse.
- Algunos firmwares pueden requerir un comando personalizado mediante el perfil.

Después de validar Cisco, Juniper y MikroTik con salidas reales, el siguiente paso será agregar validación bidireccional, ejecución por sitio o grupo y un worker para consultas fuera del proceso web.
