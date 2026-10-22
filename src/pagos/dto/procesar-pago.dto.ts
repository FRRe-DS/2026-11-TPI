import { ApiProperty } from '@nestjs/swagger';

export class ProcesarPagoDto {
  @ApiProperty({ description: 'ID del viaje proveniente de M6', example: 'viaje-789' })
  id_viaje: string;

  @ApiProperty({ description: 'ID del cliente proveniente de M2', example: 'cli-98765' })
  id_cliente: string;

  @ApiProperty({ description: 'Monto total a cobrar', example: 3250.00 })
  monto: number;

  @ApiProperty({ description: 'Tipo: COBRO_VIAJE o CARGO_CANCELACION', example: 'COBRO_VIAJE' })
  tipo_operacion: string;

  @ApiProperty({ description: 'Clave única para evitar duplicados (Idempotencia)', example: 'idem-abc-123' })
  clave_idempotencia: string;
}
