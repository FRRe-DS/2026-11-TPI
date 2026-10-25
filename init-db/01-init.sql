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

-- Tarifas iniciales
INSERT INTO parametros_tarifa 
  (tipo_vehiculo, base, por_km, por_min, minima, cargo_cancelacion, comision_pct)
VALUES 
  ('auto', 500.00, 150.00, 50.00, 800.00, 400.00, 15.00),
  ('moto', 350.00, 100.00, 35.00, 500.00, 250.00, 12.00);
  