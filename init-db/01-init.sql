-- init-db/01-init.sql
CREATE TABLE IF NOT EXISTS parametros_tarifa (
  tipo_vehiculo     ENUM('auto', 'moto') PRIMARY KEY,
  base              DECIMAL(12,2) NOT NULL CHECK (base >= 0),
  por_km            DECIMAL(12,2) NOT NULL CHECK (por_km >= 0),
  por_min           DECIMAL(12,2) NOT NULL CHECK (por_min >= 0),
  minima            DECIMAL(12,2) NOT NULL CHECK (minima >= 0),
  cargo_cancelacion DECIMAL(12,2) NOT NULL CHECK (cargo_cancelacion >= 0),
  comision_pct      DECIMAL(5,2)  NOT NULL CHECK (comision_pct BETWEEN 0 AND 100),
  actualizado_en    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS medios_pago (
  id             CHAR(36) PRIMARY KEY DEFAULT (UUID()),
  cliente_id     CHAR(36) NOT NULL,
  tipo           VARCHAR(20) NOT NULL CHECK (tipo IN ('tarjeta', 'billetera', 'efectivo')),
  alias          VARCHAR(40) NOT NULL CHECK (CHAR_LENGTH(alias) BETWEEN 1 AND 40),
  ultimos4       VARCHAR(4) NULL CHECK (ultimos4 IS NULL OR ultimos4 REGEXP '^[0-9]{4}$'),
  predeterminado BOOLEAN NOT NULL DEFAULT FALSE,
  creado_en      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS liquidaciones (
  id              CHAR(36) PRIMARY KEY DEFAULT (UUID()),
  conductor_id    CHAR(36) NOT NULL,
  desde           DATETIME NOT NULL,
  hasta           DATETIME NOT NULL,
  cantidad_viajes INT NOT NULL,
  bruto           DECIMAL(12,2) NOT NULL DEFAULT 0,
  comision        DECIMAL(12,2) NOT NULL DEFAULT 0,
  neto            DECIMAL(12,2) NOT NULL DEFAULT 0,
  estado          VARCHAR(20) NOT NULL DEFAULT 'pendiente' CHECK (estado IN ('pendiente', 'pagada', 'fallida')),
  idempotency_key VARCHAR(255) NOT NULL UNIQUE,
  creado_en       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  actualizado_en  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS pagos (
  id             CHAR(36) PRIMARY KEY DEFAULT (UUID()),
  viaje_id       VARCHAR(255) NOT NULL UNIQUE,
  cliente_id     CHAR(36) NOT NULL,
  conductor_id   CHAR(36) NULL,
  medio_pago_id  CHAR(36) NULL,
  tipo_vehiculo  ENUM('auto', 'moto') NOT NULL,
  monto_estimado DECIMAL(12,2) NOT NULL,
  monto_final    DECIMAL(12,2) NULL,
  comision_pct   DECIMAL(5,2) NULL,
  estado         ENUM('autorizado', 'rechazado', 'capturado', 'cancelado_con_cargo', 'reintegrado_parcial', 'reintegrado') NOT NULL,
  capturado_en   DATETIME NULL,
  liquidacion_id CHAR(36) NULL,
  creado_en      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  actualizado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_pagos_medio_pago FOREIGN KEY (medio_pago_id) REFERENCES medios_pago (id),
  CONSTRAINT fk_pagos_liquidacion FOREIGN KEY (liquidacion_id) REFERENCES liquidaciones (id)
);

CREATE TABLE IF NOT EXISTS operaciones_financieras (
  id              CHAR(36) PRIMARY KEY DEFAULT (UUID()),
  pago_id         CHAR(36) NOT NULL,
  tipo            VARCHAR(30) NOT NULL CHECK (tipo IN ('autorizacion', 'rechazo', 'captura', 'cargo_cancelacion', 'reintegro')),
  monto           DECIMAL(12,2) NOT NULL CHECK (monto >= 0),
  resultado       VARCHAR(10) NOT NULL CHECK (resultado IN ('ok', 'rechazado')),
  motivo          VARCHAR(255) NULL,
  idempotency_key VARCHAR(255) NOT NULL UNIQUE,
  detalle         JSON NOT NULL,
  creado_en       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_operaciones_pago FOREIGN KEY (pago_id) REFERENCES pagos (id)
);

CREATE TABLE IF NOT EXISTS reglas_tarifa (
  id                CHAR(36) PRIMARY KEY,
  tipo_vehiculo     ENUM('auto', 'moto') NOT NULL,
  tarifa_base       DECIMAL(12,2) NOT NULL CHECK (tarifa_base >= 0),
  precio_por_km     DECIMAL(12,2) NOT NULL CHECK (precio_por_km >= 0),
  precio_por_minuto DECIMAL(12,2) NOT NULL CHECK (precio_por_minuto >= 0),
  tarifa_minima     DECIMAL(12,2) NOT NULL CHECK (tarifa_minima >= 0),
  cargo_cancelacion DECIMAL(12,2) NOT NULL DEFAULT 0 CHECK (cargo_cancelacion >= 0),
  activa            BOOLEAN NOT NULL DEFAULT FALSE,
  creado_en         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  actualizado_en    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tarifas_finales (
  viaje_id       CHAR(36) PRIMARY KEY,
  regla_id       CHAR(36) NOT NULL,
  moneda         CHAR(3) NOT NULL DEFAULT 'ARS',
  desglose       JSON NOT NULL,
  calculada_en   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS pagos_contrato (
  id                CHAR(36) PRIMARY KEY,
  concepto          VARCHAR(30) NOT NULL,
  viaje_id          CHAR(36) NULL,
  reserva_id        CHAR(36) NULL,
  cliente_id        CHAR(36) NOT NULL,
  beneficiario_id   CHAR(36) NULL,
  monto             DECIMAL(12,2) NOT NULL,
  monto_reembolsado DECIMAL(12,2) NOT NULL DEFAULT 0,
  moneda            CHAR(3) NOT NULL DEFAULT 'ARS',
  metodo            VARCHAR(20) NOT NULL,
  estado            VARCHAR(30) NOT NULL,
  referencia_externa VARCHAR(255) NULL,
  creado_en         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  actualizado_en    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS movimientos_contrato (
  id       CHAR(36) PRIMARY KEY,
  pago_id  CHAR(36) NOT NULL,
  tipo     VARCHAR(30) NOT NULL,
  monto    DECIMAL(12,2) NOT NULL,
  fecha    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  actor    VARCHAR(100) NOT NULL,
  detalle  VARCHAR(500) NULL
);

CREATE TABLE IF NOT EXISTS reembolsos_contrato (
  id        CHAR(36) PRIMARY KEY,
  pago_id   CHAR(36) NOT NULL,
  monto     DECIMAL(12,2) NOT NULL,
  motivo    VARCHAR(500) NOT NULL,
  creado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS liquidaciones_contrato (
  id                 CHAR(36) PRIMARY KEY,
  beneficiario_id    CHAR(36) NOT NULL,
  periodo_desde      DATE NOT NULL,
  periodo_hasta      DATE NOT NULL,
  pago_ids           JSON NOT NULL,
  monto_bruto        DECIMAL(12,2) NOT NULL,
  comision_plataforma DECIMAL(12,2) NOT NULL,
  cobrado_en_efectivo DECIMAL(12,2) NOT NULL,
  monto_neto         DECIMAL(12,2) NOT NULL,
  moneda             CHAR(3) NOT NULL DEFAULT 'ARS',
  estado             VARCHAR(20) NOT NULL,
  referencia_transferencia VARCHAR(100) NULL,
  creada_en          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  actualizada_en     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS operaciones_idempotentes (
  clave       VARCHAR(255) PRIMARY KEY,
  ruta        VARCHAR(255) NOT NULL,
  cuerpo_hash CHAR(64) NOT NULL,
  estado_http INT NOT NULL,
  respuesta   JSON NOT NULL,
  creado_en   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Tarifas iniciales
INSERT INTO parametros_tarifa 
  (tipo_vehiculo, base, por_km, por_min, minima, cargo_cancelacion, comision_pct)
VALUES 
  ('auto', 500.00, 150.00, 50.00, 800.00, 400.00, 15.00),
  ('moto', 350.00, 100.00, 35.00, 500.00, 250.00, 12.00);

INSERT INTO reglas_tarifa
  (id, tipo_vehiculo, tarifa_base, precio_por_km, precio_por_minuto, tarifa_minima,
   cargo_cancelacion, activa)
SELECT UUID(), tipo_vehiculo, base, por_km, por_min, minima, cargo_cancelacion, TRUE
FROM parametros_tarifa
WHERE NOT EXISTS (SELECT 1 FROM reglas_tarifa);
  