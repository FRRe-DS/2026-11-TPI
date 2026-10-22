import { ApiProperty } from '@nestjs/swagger';

export class CreateTarifaDto {
  @ApiProperty({ description: 'Identificador de la reserva (M9)', example: 'res-12345' })
  id_reserva: string;

  @ApiProperty({ description: 'Tipo de vehículo (AUTO o MOTO)', example: 'AUTO' })
  tipo_vehiculo: string;

  @ApiProperty({ description: 'Distancia en kilómetros (M4)', example: 15.5 })
  distancia_km: number;

  @ApiProperty({ description: 'Tiempo estimado en minutos', example: 25 })
  tiempo_minutos: number;
}