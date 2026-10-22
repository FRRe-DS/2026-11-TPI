import { Controller, Get, Post, Body, Param } from '@nestjs/common';
import { ApiTags, ApiOperation, ApiResponse, ApiParam } from '@nestjs/swagger';
import { PagosService } from './pagos.service';
import { ProcesarPagoDto } from './dto/procesar-pago.dto';

@ApiTags('Pagos y Liquidaciones')
@Controller('api/pagos')
export class PagosController {
  constructor(private readonly pagosService: PagosService) {}

  @Post('procesar')
  @ApiOperation({ summary: 'Procesar un cobro de viaje o cargo de cancelación' })
  @ApiResponse({ status: 201, description: 'Transacción procesada y registrada.' })
  procesar(@Body() procesarPagoDto: ProcesarPagoDto) {
    return this.pagosService.procesar(procesarPagoDto);
  }

  @Get('historial/:idCliente')
  @ApiOperation({ summary: 'Obtener historial financiero completo de un cliente' })
  @ApiParam({ name: 'idCliente', description: 'ID del cliente (M2)' })
  @ApiResponse({ status: 200, description: 'Historial devuelto exitosamente.' })
  obtenerHistorial(@Param('idCliente') idCliente: string) {
    return this.pagosService.obtenerHistorial(idCliente);
  }
}