import { ApiProperty } from '@nestjs/swagger';

export class CreateMetodoPagoDto {
  @ApiProperty({ description: 'Identificador del cliente (proveniente de M2)', example: 'cli-98765' })
  id_cliente: string;

  @ApiProperty({ description: 'Tipo de medio de pago', example: 'TARJETA' })
  tipo: string;

  @ApiProperty({ description: 'Últimos 4 dígitos para enmascarar (opcional)', example: '4567', required: false })
  ultimos_cuatro_digitos?: string;

  @ApiProperty({ description: 'Proveedor del servicio', example: 'VISA' })
  proveedor: string;
}