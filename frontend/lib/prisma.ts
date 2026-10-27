import { PrismaClient } from '@prisma/client'
import { PrismaPg } from '@prisma/adapter-pg'
import { Pool } from 'pg'

const globalForPrisma = global as unknown as {
  prisma: PrismaClient | undefined
  pool: Pool | undefined
}

// Create a simple connection pool for the adapter
// Prisma handles most connection pooling internally
if (!globalForPrisma.pool) {
  globalForPrisma.pool = new Pool({
    connectionString: process.env.DATABASE_URL,
  })
}

const adapter = new PrismaPg(globalForPrisma.pool)

if (!globalForPrisma.prisma) {
  globalForPrisma.prisma = new PrismaClient({
    adapter,
  })
}

export const prisma = globalForPrisma.prisma
