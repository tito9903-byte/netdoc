# Descubrimiento de conexiones LLDP por SSH

## Objetivo

NetDoc puede consultar un dispositivo por SSH, ejecutar el comando LLDP apropiado para su plataforma y comparar los vecinos anunciados con los dispositivos e interfaces registrados en NetBox.

El módulo no crea cables automáticamente durante la consulta. El flujo es:

1. conectarse por SSH usando una cuenta de solo lectura;
2. ejecutar LLDP;
3. normalizar la salida;
4. identificar el dispositivo y la interfaz remota en NetBox;
5. verificar que ambos extremos estén libres;
6. presentar una propuesta;
7. crear el cable únicamente después de la confirmación del usuario.

Un solo cable de NetBox documenta los dos extremos. NetDoc no crea una conexión duplicada en el dispositivo remoto.

## Plataformas de la primera fase

- Arista EOS;
- Cisco IOS e IOS XE;
- Cisco NX-OS;
- Juniper Junos;
- MikroTik RouterOS.

Netmiko administra la sesión CLI y solicita a NTC Templates una salida estructurada cuando existe una plantilla compatible. Si la plataforma devuelve texto, NetDoc utiliza parsers de respaldo para formatos comunes de Cisco, Arista, Junos y RouterOS.

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
NETDOC_SSH_PROFILES_JSON='{"default":{"username":"netdoc-read","password":"CAMBIAR","port":22},"arista_eos":{},"cisco_ios":{},"cisco_nxos":{},"juniper_junos":{},"mikrotik_routeros":{}}'
```

El perfil `default` se hereda. Cada plataforma puede reemplazar cualquier valor:

```env
NETDOC_SSH_PROFILES_JSON='{"default":{"username":"netdoc-read","password":"CLAVE_GENERAL","port":22},"arista_eos":{"username":"netdoc-arista","password":"CLAVE_ARISTA"},"juniper_junos":{"private_key_file":"/etc/netdoc/ssh/juniper_read"}}'
```

Campos admitidos dentro de cada perfil:

- `username`;
- `password`;
- `private_key_file` o `key_file`;
- `secret`, cuando la plataforma lo requiera;
- `port`;
- `device_type`, para sobrescribir el controlador de Netmiko;
- `command`, para usar una variante específica del comando LLDP.

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

1. una IP principal IPv4 o IPv6 accesible desde el servidor de NetDoc;
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
6. Revisar cada propuesta.
7. Seleccionar el tipo físico del cable.
8. Pulsar **Confirmar y documentar**.

## Estados de una propuesta

### Lista para confirmar

- existe la interfaz local en NetBox;
- el vecino coincide con un dispositivo;
- existe la interfaz remota;
- ambos extremos están libres.

### Interfaz ocupada en NetBox

Alguno de los extremos ya tiene un cable o un extremo conectado. NetDoc no sobrescribe la conexión.

### Requiere revisión

No se pudo identificar de forma segura el dispositivo remoto o su interfaz. En esta primera fase no se permite forzar una conexión sin coincidencia.

## Confianza

La puntuación combina:

- coincidencia exacta del nombre;
- coincidencia del nombre sin dominio DNS;
- coincidencia de la IP de administración anunciada con la IP principal;
- coincidencia de la interfaz local;
- coincidencia de la interfaz remota.

La confianza ayuda a ordenar la revisión, pero no sustituye la confirmación humana.

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
- Las contraseñas, llaves y salida completa del equipo no se guardan en la auditoría.

## Limitaciones de la primera fase

- El descubrimiento se ejecuta por un dispositivo a la vez.
- La solicitud web espera a que termine el comando SSH.
- No existe todavía validación bidireccional automática desde el vecino.
- No se crean dispositivos o interfaces faltantes desde LLDP.
- No se eliminan cables cuando un vecino deja de anunciarse.
- Algunos firmwares pueden requerir un comando o parser específico mediante el perfil.

Cuando el flujo manual quede validado con equipos reales, el siguiente paso será mover las consultas a un worker, agregar validación bidireccional y permitir descubrimiento por sitio o grupo.
