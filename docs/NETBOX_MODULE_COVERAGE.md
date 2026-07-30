# Cobertura de módulos de NetBox

## Propósito

Este documento evita copiar NetBox sin criterio y define cómo cada dominio se transformará en un flujo más sencillo dentro de NetDoc. Los estados describen la cobertura de NetDoc, no la disponibilidad del módulo en NetBox.

Estados:

- **Operativo:** disponible en NetDoc y probado con datos reales o simulados.
- **En revisión:** implementado en la rama actual y pendiente de revisión completa.
- **Fundamento:** existen servicios o planes, pero no una experiencia completa.
- **Planificado:** analizado y pendiente de implementación.
- **Fuera de alcance inicial:** no se habilitará todavía por riesgo o baja prioridad.

## Infraestructura física y DCIM

| Objeto o proceso | Estado | Experiencia objetivo | Reglas principales |
|---|---|---|---|
| Regiones y grupos de sitios | Planificado | Árbol territorial reutilizable | No crear duplicados por nombre/slug |
| Sitios | En revisión | Catálogo, alta, edición y retiro | Nombre/slug únicos, permisos, CSRF y sin eliminación |
| Localidades | Fundamento | Administrar dentro del sitio | Exigir sitio y jerarquía correcta |
| Racks | En revisión | Listado, ficha, alta, 2D y 3D | Altura, numeración, cara y conflictos |
| Reservas de rack | Planificado | Calendario de unidades reservadas | No permitir solapamientos |
| Fabricantes | En revisión | Catálogo, ficha, creación y edición | Evitar variantes duplicadas; sin eliminación inicial |
| Modelos de equipos | En revisión | Catálogo, ficha, edición, imágenes y equipos asociados | Dimensiones y componentes reutilizables |
| Tipos de módulos | Planificado | Biblioteca de tarjetas y módulos | Compatibilidad con bahías |
| Dispositivos | Operativo / en revisión | Búsqueda, ficha y alta física guiada | Modelo, rol, sitio, rack y estado |
| Módulos instalados | Planificado | Insertar tarjeta en bahía disponible | Validar tipo y bahía compatible |
| Inventario interno | Planificado | Seriales, piezas y activos por equipo | Jerarquía y duplicados |
| Interfaces | Operativo | Consulta y detalle | Estado, tipo, LAG, VLAN, IP y cable |
| Plantillas de interfaces | En revisión | Generador masivo por patrón | Vista previa y máximo controlado |
| Consola | Planificado | Conectar consola y servidor de consola | Extremos compatibles y libres |
| Energía | Planificado | Puertos, tomas, paneles y feeds | Tensión, fase, capacidad y trazado |
| Patch panels | Planificado | Puertos frontales/traseros y mapeo | Posiciones y pares válidos |
| Cables | Operativo / fundamento IA | Crear y consultar conexión física | Extremos libres, distintos y compatibles |
| Trazado de cables | Planificado | Mostrar trayecto completo | Solo lectura durante primera etapa |

## IPAM y servicios de red

| Objeto o proceso | Estado | Experiencia objetivo | Reglas principales |
|---|---|---|---|
| VRF | Planificado | Catálogo, ficha y asistente | RD único cuando aplique |
| Route targets | Planificado | Selector reutilizable | Importación/exportación coherentes |
| Prefijos | En revisión de lectura | Pools, localidad y ocupación | VRF, jerarquía, solapamiento y estado |
| Rangos IP | En revisión de lectura | Reservas y ocupación | Dentro del prefijo y sin duplicados |
| Direcciones IP | En revisión de lectura | Buscar, asignar y liberar | Duplicados, VRF, NAT y objeto asignado |
| VLAN | Planificado | Crear grupo, VLAN y alcance | VID, grupo, sitio y tenant |
| Grupos de VLAN | Planificado | Catálogo por localidad | Rango y alcance |
| Roles IPAM | En revisión de lectura | Filtro y clasificación | No inventar significados |
| RIR | Planificado | Bloques agregados y responsables | Jerarquía y fechas |
| ASN y rangos ASN | Planificado | Asignación por RIR y tenant | Evitar solapamiento |
| FHRP | Planificado | Grupo, VIP y miembros | Autenticación y prioridades |
| Servicios | Planificado | Servicio por equipo o VM | Puerto, protocolo e IP |
| Plantillas de servicios | Planificado | Reutilización al crear equipos | Validar dependencias |
| L2VPN | Planificado | Instancia y terminaciones | Tipo y terminaciones compatibles |

## Circuitos y proveedores

| Objeto o proceso | Estado | Experiencia objetivo | Reglas principales |
|---|---|---|---|
| Proveedores | Planificado | Catálogo y contactos | Nombre/slug únicos |
| Cuentas de proveedor | Planificado | Contratos por proveedor | Tenant, cuenta y fechas |
| Tipos de circuito | Planificado | Plantillas de Internet/transporte | Slug único |
| Circuitos | Fundamento | Alta guiada con CID y commit rate | Proveedor, tipo, estado y tenant |
| Terminaciones A/Z | Planificado | Asistente visual | Sitio, proveedor/red y puerto |
| Conexión física del circuito | Planificado | Cablear terminación a interfaz | Extremos compatibles y libres |
| Grupos de circuitos | Planificado | Agrupar redundancia y propósito | Membresía y prioridad |

## Virtualización

| Objeto o proceso | Estado | Experiencia objetivo | Reglas principales |
|---|---|---|---|
| Tipos y grupos de clúster | Planificado | Biblioteca | Nombre/slug únicos |
| Clústeres | Planificado | Ficha de capacidad | Sitio/grupo/tenant |
| Máquinas virtuales | Planificado | Alta y ficha | Clúster, rol, plataforma y recursos |
| Interfaces de VM | Planificado | Crear y conectar | MAC, VLAN, IP y LAG virtual |
| Discos virtuales | Planificado | Capacidad por VM | Tamaño no negativo |

## VPN e inalámbrico

| Objeto o proceso | Estado | Experiencia objetivo | Reglas principales |
|---|---|---|---|
| Túneles y terminaciones | Planificado | Asistente por extremos | Túnel antes que terminaciones |
| IKE/IPSec | Planificado | Perfiles reutilizables | Propuestas y políticas compatibles |
| WLAN y grupos | Planificado | Catálogo por sitio | SSID, autenticación y alcance |
| Enlaces inalámbricos | Planificado | Extremos y parámetros RF | Interfaces inalámbricas compatibles |

## Automatización y personalización

| Objeto o proceso | Estado | Experiencia objetivo | Reglas principales |
|---|---|---|---|
| Contextos de configuración | Planificado | Editor guiado y vista renderizada | Precedencia y alcance |
| Plantillas de configuración | Planificado | Biblioteca y renderizado | Sintaxis y contexto |
| Journal | Planificado | Notas humanas desde cada ficha | Autor y objeto visibles |
| Etiquetas | Planificado | Selector y administración | Slug, color y alcance |
| Campos personalizados | Planificado | Renderizado dinámico desde esquema | Respetar tipo y validación |
| Event rules y webhooks | Fuera de alcance inicial | Consulta y diagnóstico | No crear automatización sin revisión |
| Scripts personalizados | Fuera de alcance inicial | Ejecutar solo scripts aprobados | Nunca aceptar código generado libremente |
| Plugins | Solo descubrimiento | Detectar objetos y rutas instaladas | No asumir esquemas del core |
| Historial de cambios | Planificado | Línea temporal unificada | Solo lectura y enlaces al objeto |

## Administración

La administración de usuarios, grupos, permisos y tokens de **NetBox** no será replicada inicialmente. NetDoc administra sus propias cuentas y permisos, mientras el token técnico de NetBox se configura fuera de la interfaz y bajo mínimo privilegio.

No se permitirá al asistente:

- crear o elevar usuarios de NetBox;
- administrar tokens;
- conceder permisos;
- instalar plugins;
- ejecutar scripts arbitrarios;
- modificar la configuración del servidor.

## Orden de implementación

1. Finalizar editores de componentes, fabricantes, modelos y racks.
2. Consolidar conexiones físicas y trazado.
3. Agregar sitios y localidades como flujo administrable.
4. Implementar VLAN, prefijos, rangos y direcciones con prevalidación.
5. Implementar proveedores, circuitos y terminaciones.
6. Agregar módulos/tarjetas e inventario.
7. Incorporar virtualización, VPN y servicios.
8. Habilitar asistente de solo lectura.
9. Habilitar creación de cables mediante planes confirmados.
10. Extender el asistente a flujos compuestos después de pruebas y permisos específicos.
