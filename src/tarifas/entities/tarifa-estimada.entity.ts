import { Entity, Column, PrimaryGeneratedColumn, CreateDateColumn } from 'typeorm';

@Entity('tarifa_estimada')
export class TarifaEstimada {
  @PrimaryGeneratedColumn()
  id: number;

  @Column({ name: 'id_reserva', type: 'varchar', length: 255 })
  idReserva: string;

  @Column({ name: 'tipo_vehiculo', type: 'varchar', length: 50 })
  tipoVehiculo: string;

  @Column({ name: 'distancia_km', type: 'decimal', precision: 10, scale: 2 })
  distanciaKm: number;

  @Column({ name: 'tiempo_minutos', type: 'int' })
  tiempoMinutos: number;

  @Column({ name: 'monto_estimado', type: 'decimal', precision: 10, scale: 2 })
  montoEstimado: number;

  @CreateDateColumn({ name: 'fecha_creacion' })
  fechaCreacion: Date;
}