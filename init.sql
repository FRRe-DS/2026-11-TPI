CREATE DATABASE IF NOT EXISTS m7_tarifas_pagos;
USE m7_tarifas_pagos;

CREATE TABLE IF NOT EXISTS tarifa_estimada (
    id INT AUTO_INCREMENT PRIMARY KEY,
    id_reserva VARCHAR(255) NOT NULL,
    tipo_vehiculo VARCHAR(50) NOT NULL,
    distancia_km DECIMAL(10,2) NOT NULL,
    tiempo_minutos INT NOT NULL,
    monto_estimado DECIMAL(10,2) NOT NULL,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);