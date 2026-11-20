/* =====================================================================
   Proyecto: RPA Invoice Processing (UiPath + SQL Server)
   Script  : 01_crear_base_datos.sql
   Ejecutar en SSMS con un usuario administrador (por ejemplo sa).
   ===================================================================== */

-- 1. Base de datos ----------------------------------------------------
USE master;
GO
IF DB_ID('RPA_Facturas') IS NULL
    CREATE DATABASE RPA_Facturas;
GO
USE RPA_Facturas;
GO

-- 2. Tablas -----------------------------------------------------------

-- Registro de cada corrida del robot
IF OBJECT_ID('dbo.LogEjecuciones') IS NULL
CREATE TABLE dbo.LogEjecuciones (
    id                INT IDENTITY(1,1) PRIMARY KEY,
    inicio            DATETIME2     NOT NULL DEFAULT SYSDATETIME(),
    fin               DATETIME2     NULL,
    total_procesadas  INT           NOT NULL DEFAULT 0,
    total_validas     INT           NOT NULL DEFAULT 0,
    total_rechazadas  INT           NOT NULL DEFAULT 0,
    total_duplicadas  INT           NOT NULL DEFAULT 0,
    estado            NVARCHAR(20)  NOT NULL DEFAULT 'EN_CURSO',
    CONSTRAINT CK_LogEjecuciones_estado
        CHECK (estado IN ('EN_CURSO', 'FINALIZADA', 'ERROR'))
);
GO

-- Catálogo de proveedores
IF OBJECT_ID('dbo.Proveedores') IS NULL
CREATE TABLE dbo.Proveedores (
    id      INT IDENTITY(1,1) PRIMARY KEY,
    nombre  NVARCHAR(150) NOT NULL,
    rfc     NVARCHAR(20)  NOT NULL,
    activo  BIT           NOT NULL DEFAULT 1,
    CONSTRAINT UQ_Proveedores_nombre UNIQUE (nombre),
    CONSTRAINT UQ_Proveedores_rfc    UNIQUE (rfc)
);
GO

-- Facturas procesadas
IF OBJECT_ID('dbo.Facturas') IS NULL
CREATE TABLE dbo.Facturas (
    id              INT IDENTITY(1,1) PRIMARY KEY,
    proveedor_id    INT            NOT NULL,
    numero_factura  NVARCHAR(50)   NOT NULL,
    fecha_factura   DATE           NOT NULL,
    subtotal        DECIMAL(18,2)  NOT NULL,
    iva             DECIMAL(18,2)  NOT NULL,
    total           DECIMAL(18,2)  NOT NULL,
    estado          NVARCHAR(20)   NOT NULL DEFAULT 'VALIDA',
    fecha_proceso   DATETIME2      NOT NULL DEFAULT SYSDATETIME(),
    archivo_origen  NVARCHAR(260)  NOT NULL,
    ejecucion_id    INT            NULL,
    CONSTRAINT FK_Facturas_Proveedores
        FOREIGN KEY (proveedor_id) REFERENCES dbo.Proveedores(id),
    CONSTRAINT FK_Facturas_LogEjecuciones
        FOREIGN KEY (ejecucion_id) REFERENCES dbo.LogEjecuciones(id),
    -- Regla anti-duplicados: mismo proveedor + mismo número de factura
    CONSTRAINT UQ_Facturas_proveedor_numero
        UNIQUE (proveedor_id, numero_factura),
    CONSTRAINT CK_Facturas_estado
        CHECK (estado IN ('VALIDA', 'RECHAZADA')),
    CONSTRAINT CK_Facturas_montos
        CHECK (subtotal >= 0 AND iva >= 0 AND total >= 0
               AND ABS(subtotal + iva - total) <= 0.01)
);
GO

-- Excepciones y errores del robot
IF OBJECT_ID('dbo.Excepciones') IS NULL
CREATE TABLE dbo.Excepciones (
    id            INT IDENTITY(1,1) PRIMARY KEY,
    ejecucion_id  INT            NULL,
    archivo       NVARCHAR(260)  NOT NULL,
    tipo_error    NVARCHAR(20)   NOT NULL,
    detalle       NVARCHAR(500)  NOT NULL,
    fecha         DATETIME2      NOT NULL DEFAULT SYSDATETIME(),
    CONSTRAINT FK_Excepciones_LogEjecuciones
        FOREIGN KEY (ejecucion_id) REFERENCES dbo.LogEjecuciones(id),
    CONSTRAINT CK_Excepciones_tipo
        CHECK (tipo_error IN ('NEGOCIO', 'SISTEMA'))
);
GO

-- 3. Datos de ejemplo (proveedores ficticios) -------------------------
IF NOT EXISTS (SELECT 1 FROM dbo.Proveedores)
INSERT INTO dbo.Proveedores (nombre, rfc, activo) VALUES
    (N'Suministros del Norte SA de CV',  N'SNO010101AB1', 1),
    (N'Papelería Central SA de CV',      N'PCE020202CD2', 1),
    (N'Tecnología Integral SA de CV',    N'TIN030303EF3', 1),
    (N'Servicios Logísticos MX SA de CV',N'SLM040404GH4', 1),
    (N'Mantenimiento Express SA de CV',  N'MEX050505IJ5', 0);  -- inactivo, para probar validación
GO

-- 4. Usuario dedicado para el robot (no usar sa en UiPath) ------------
USE master;
GO
IF NOT EXISTS (SELECT 1 FROM sys.server_principals WHERE name = 'rpa_user')
    CREATE LOGIN rpa_user
        WITH PASSWORD = 'CambiaEstaClave#2026', CHECK_POLICY = ON;
GO
USE RPA_Facturas;
GO
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = 'rpa_user')
    CREATE USER rpa_user FOR LOGIN rpa_user;
GO
ALTER ROLE db_datareader ADD MEMBER rpa_user;
ALTER ROLE db_datawriter ADD MEMBER rpa_user;
GO

-- 5. Verificación -----------------------------------------------------
SELECT name AS tabla FROM sys.tables ORDER BY name;
SELECT * FROM dbo.Proveedores;
GO