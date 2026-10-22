import { Entity, Column, PrimaryGeneratedColumn, CreateDateColumn } from 'typeorm';

@Entity('pago')
export class Pago {
  @PrimaryGeneratedColumn()
  id: number;

  @Column({ name: 'id_viaje', type: 'varchar', length: 255 })
  idViaje: string;

  @Column({ name: 'id_cliente', type: 'varchar', length: 255 })
  idCliente: string;

  @Column({ type: 'decimal', precision: 10, scale: 2 })
  monto: number;

  @Column({ name: 'monto_conductor', type: 'decimal', precision: 10, scale: 2, nullable: true })
  montoConductor: number;

  @Column({ type: 'varchar', length: 50 })
  estado: string; // APROBADO, RECHAZADO, REINTEGRADO

  @Column({ name: 'tipo_operacion', type: 'varchar', length: 50 })
  tipoOperacion: string; // COBRO_VIAJE o CARGO_CANCELACION

  @Column({ name: 'clave_idempotencia', type: 'varchar', length: 255, unique: true })
  claveIdempotencia: string;

  @CreateDateColumn({ name: 'fecha_creacion' })
  fechaCreacion: Date;
}